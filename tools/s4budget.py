#!/usr/bin/env python3
"""
s4budget — ROM/RAM/VRAM budget dashboard for the Aeon engine.

Reads the listing sigil emits (`sigil build --emit-lst`), the game's declared
placement contract (`games/<game>/map.toml`) and the generated VRAM map, and
reports what each budget is actually spending.

    python3 tools/s4budget.py s4.lst s4.bin --map games/sonic4/map.toml
    python3 tools/s4budget.py s4.lst s4.bin --map games/sonic4/map.toml --summary

REWRITTEN 2026-08-18 for the sigil listing format. WHY, because the shape of
the old defect is worth keeping in view:

The previous parser modelled an AS Macro Assembler listing — page headers
(`AS V1.42 ...`), nested `include` depth markers, per-file byte contributions,
`__BUDGET_*` sentinel labels, `FFFFFFFFFFFF`-sign-extended RAM equates, and a
`-`-typed constant bucket it computed the whole VRAM report from. A sigil
listing has NONE of that. It is two views of one flat table:

    (0) 1/0 :        Vectors:            <- source rows, one per symbol
    ...
      Symbol Table (* = unused):
      --------------------------

     Vectors : 0 C |                     <- symbol rows, same set, same order
     ...
       2182 symbols
        0 unused symbols

Every symbol is type `C`; there are no constants, no includes, no sentinels and
no page breaks. So the old parser matched nothing, produced an empty model, and
the tool printed `RAM: 0KB/64KB (0%)` — a healthy-looking measurement of a dead
parser (tools lens sweep D7). Its 40-test suite could not catch that: every
fixture was hand-authored WITH AS page headers, so fixture and parser were
co-designed and the suite was green forever.

The three defences against a repeat, all structural rather than conventional:

  1. `parse_listing` VALIDATES. A listing that does not carry a symbol-table
     header, a `N symbols` trailer, and exactly N parsed rows in BOTH halves
     raises `ListingFormatError`. There is no path from "format changed" to
     "zero" — a format this cannot read stops the tool.
  2. UNMEASURED is never rendered as a number. Axes with no source say so.
  3. The tests are excerpted from real `s4.lst` / `demo.lst` builds, not
     hand-authored, plus poison fixtures asserting (1).

What is measurable, and from where:

  ROM total      the ROM file on disk, against `[[region]] rom`'s size.
                 `EndOfRom` cross-checks it — see the next paragraph for what
                 that cross-check is now, and what it used to be.

THE `EndOfRom` CROSS-CHECK IS AN ACCOUNTING NOW, AND USED TO BE A NOTE
(2026-09-06, the sigil lane's F-class row F4). `format_rom_report` compared
`EndOfRom` with the ROM file's size and, on a disagreement, printed

    NOTE: EndOfRom and the ROM file differ by N bytes (padding, or a stale file).

That line was never appended to `breaches`, so it could not fail a build, and its
own parenthesis names two causes with opposite severities — legitimate padding and
a stale artifact — without separating them. A third cause it did not name, real
content placed past the assembled image, read identically. WORSE THAN UN-FAILABLE:
build.sh invokes this tool with `--summary`, and `format_summary` never received
`endofrom` at all, so under the flag the build actually uses the line was not even
PRINTED. The disagreement is not small or hypothetical — it is 42,845 B in `s4.bin`
and 54,592 B in `s4.debug.bin` at the measurement below, i.e. the NOTE fired on
every canonical build and said nothing.

`classify_rom_tail` replaces it with an accounting that has a failing branch:

  · `rom_size < EndOfRom` — the image on disk is SHORTER than what was assembled.
    There is no legitimate cause; it is a truncated or stale file. BREACH.
  · excess begins with the appendix magic `DE B2` — the convsym deb2 symbol table
    sigil appends at `EndOfRom` (crates/sigil-harness/src/native.rs
    `append_deb2_appendix`; both canonical shapes carry it since the 2026-08-04
    crash-report ruling). ACCOUNTED, size reported.
    ⚠ The magic is the BYTE PAIR `DE B2`, not the ASCII string `deb2`, which
    appears in neither ROM — see build.sh's own corrected note above the sigil
    invocation, and error_handler.emp's `cmpi.w #$DEB2,(a1)+` description.
  · every excess byte equals the map's declared `fill` — padding. ACCOUNTED.
  · anything else — unaccounted content past the assembled image. BREACH, naming
    the offset of the first byte that is neither.

Measured at introduction, all three shapes that build here: s4 777,362/820,207
(42,845 B, `de b2`), s4.debug 791,796/846,388 (54,592 B, `de b2`), demo
70,170/96,827 (26,657 B, `de b2`). Every one lands in the ACCOUNTED-appendix
branch, so no correct run of any shipped shape trips the refusal.
  Budgets        `[[budget]]` in map.toml — region + ceiling + a cursor SYMBOL,
                 resolved against the listing. This is the map-owned successor
                 to the retired `__BUDGET_DATA` sentinel. Note sigil ALSO
                 enforces these at pack time, so the gate below is a dashboard
                 and a second pair of eyes, not the primary enforcer.
  RAM            symbols at >= $FFFF0000, sized by the gap to their successor.
                 Genuinely measurable, and was the axis the dead parser lost.
  VRAM           NOT in the listing at all (no constants are emitted). Sourced
                 from `tools/vram_map.py`, the generated mirror of
                 `games/sonic4/vram.toml` that is already this tree's single
                 VRAM authority. sonic4 only; unmeasured elsewhere, loudly.

Per-file ROM contributions are gone and are not coming back from this input:
the listing carries no file attribution whatsoever. Nothing is reported in
their place, rather than a plausible-looking substitute.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from typing import Dict, List, NamedTuple, Optional, Set, Tuple

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


class ListingFormatError(Exception):
    """The listing is not a format this tool can read.

    Raised rather than returning an empty model, because an empty model is what
    printed `RAM: 0KB/64KB (0%)` for months. Callers may catch it; they may not
    ignore it.
    """


# ---------------------------------------------------------------------------
# Listing parser (sigil `--emit-lst` format)
# ---------------------------------------------------------------------------

class Symbol(NamedTuple):
    name: str
    value: int
    kind: str        # 'C' (computed/label) or '-' (absolute) — sigil emits only 'C' today
    unused: bool


class Listing(NamedTuple):
    symbols: List[Symbol]
    by_name: Dict[str, int]
    declared_count: int
    unused_count: int


# ` Player_Blocks : FFFFB83E C |`   (a leading `*` marks an unused symbol)
_SYM_ROW_RE = re.compile(r'^\s*(\*?)([\w.$]+)\s*:\s*([0-9A-Fa-f]+)\s+([C\-])\s*\|\s*$')
# `(0) 2175/FFFFB83E :        Player_Blocks:`
_SRC_ROW_RE = re.compile(r'^\((\d+)\)\s*(\d+)\s*/\s*([0-9A-Fa-f]+)\s*:\s+(\S.*):$')
_SYMTAB_HEADER_RE = re.compile(r'^\s*Symbol Table \(\* = unused\):\s*$')
_SYMCOUNT_RE = re.compile(r'^\s*(\d+) symbols\s*$')
_UNUSEDCOUNT_RE = re.compile(r'^\s*(\d+) unused symbols\s*$')

_RAM_BASE = 0xFFFF0000          # Genesis work RAM, 64 KB
_UPPER_RAM_START = 0xFFFF8000
_MAX_ROM_ADDR = 0x400000

#: The convsym symbol-appendix magic sigil writes at `EndOfRom`. NOT the ASCII
#: string `deb2`: the vendored MD Debugger blob validates the table it addressed
#: with `cmpi.w #$DEB2,(a1)+` (engine/debug/error_handler.emp's WARNING block),
#: i.e. a 16-bit immediate, so the bytes on disk are DE B2. build.sh carries the
#: measurement that separates the two — `s4.bin` holds 0 occurrences of ASCII
#: `deb2` and 3 of the byte pair — and the note on how the wrong claim got there.
_DEB2_MAGIC = b"\xDE\xB2"

#: The default ROM fill when no map declares one. Both shipped maps say
#: `fill = 0x00`; this is only the value used when `--map` was not given, and the
#: padding verdict says so rather than presenting it as the contract's.
_DEFAULT_FILL = 0x00


def parse_listing(lines: List[str]) -> Listing:
    """Parse a sigil listing, or raise `ListingFormatError` trying.

    Both halves are read and CROSS-CHECKED against each other and against the
    trailer's own count. That is the point: a partial parse (the D7 failure) can
    no longer look like a successful one, because three independently-produced
    numbers have to agree, and the listing supplies all three itself — none is a
    literal copied into this file.
    """
    header_idx: Optional[int] = None
    for i, line in enumerate(lines):
        if _SYMTAB_HEADER_RE.match(line):
            header_idx = i
            break
    if header_idx is None:
        raise ListingFormatError(
            "no 'Symbol Table (* = unused):' header found. This tool reads the "
            "listing sigil emits with --emit-lst; an AS-era .lst, a truncated file "
            "or a future sigil format will land here. It is deliberately fatal: "
            "returning an empty model is how this tool came to print "
            "'RAM: 0KB/64KB (0%)' against a listing it could not read at all.")

    # --- source rows (above the header): one per symbol, address + name ---
    src_rows: List[Tuple[str, int]] = []
    for line in lines[:header_idx]:
        m = _SRC_ROW_RE.match(line)
        if m:
            src_rows.append((m.group(4), int(m.group(3), 16)))

    # --- symbol rows (below the header) + the trailer counts ---
    symbols: List[Symbol] = []
    declared: Optional[int] = None
    unused_declared: Optional[int] = None
    for line in lines[header_idx + 1:]:
        mc = _SYMCOUNT_RE.match(line)
        if mc:
            declared = int(mc.group(1))
            continue
        mu = _UNUSEDCOUNT_RE.match(line)
        if mu:
            unused_declared = int(mu.group(1))
            continue
        m = _SYM_ROW_RE.match(line)
        if m:
            star, name, raw, kind = m.groups()
            symbols.append(Symbol(name=name, value=int(raw, 16), kind=kind,
                                  unused=star == "*"))

    if declared is None:
        raise ListingFormatError(
            "no '<N> symbols' trailer found after the symbol table. Without it "
            "there is nothing to check a partial parse against, and a partial "
            "parse is indistinguishable from a small program.")
    if len(symbols) != declared:
        raise ListingFormatError(
            f"symbol-table parse is INCOMPLETE: the listing declares {declared} "
            f"symbols and {len(symbols)} rows parsed. The row format this tool "
            f"expects is ` NAME : HEXVAL C |`.")
    if len(src_rows) != declared:
        raise ListingFormatError(
            f"source-listing parse is INCOMPLETE: {len(src_rows)} source rows "
            f"parsed against {declared} declared symbols. The row format this "
            f"tool expects is `(0) N/HEXADDR :        Name:`.")
    if declared == 0:
        raise ListingFormatError(
            "the listing declares 0 symbols — there is no build in here to measure.")

    # The two halves must agree symbol-for-symbol. They are two renderings of one
    # table, so any disagreement means one of the two regexes is reading something
    # it should not be, which is exactly how a wrong number gets a confident row.
    sym_pairs = [(s.name, s.value) for s in symbols]
    if src_rows != sym_pairs:
        first = next((i for i, (a, b) in enumerate(zip(src_rows, sym_pairs)) if a != b),
                     min(len(src_rows), len(sym_pairs)))
        raise ListingFormatError(
            f"the source rows and the symbol table disagree at entry {first}: "
            f"{src_rows[first] if first < len(src_rows) else '<none>'} vs "
            f"{sym_pairs[first] if first < len(sym_pairs) else '<none>'}. They are "
            f"two views of one table; a mismatch means this parser is misreading "
            f"one of them.")

    return Listing(
        symbols=symbols,
        by_name={s.name: s.value for s in symbols},
        declared_count=declared,
        unused_count=unused_declared if unused_declared is not None
        else sum(1 for s in symbols if s.unused),
    )


def rom_labels(listing: Listing) -> Dict[str, int]:
    return {s.name: s.value for s in listing.symbols if s.value < _MAX_ROM_ADDR}


def ram_labels(listing: Listing) -> Dict[str, int]:
    return {s.name: s.value for s in listing.symbols if s.value >= _RAM_BASE}


# ---------------------------------------------------------------------------
# The declared placement contract (games/<game>/map.toml)
# ---------------------------------------------------------------------------

class MapRegion(NamedTuple):
    name: str
    lma_base: int
    size: int
    kind: str


class MapBudget(NamedTuple):
    region: str
    ceiling: int
    cursor: str


class MapModel(NamedTuple):
    path: str
    regions: List[MapRegion]
    budgets: List[MapBudget]
    #: The map's top-level `fill = 0x..`, or None when it declares none. Read
    #: rather than assumed so the padding verdict in `classify_rom_tail` is
    #: against the byte the CONTRACT names, not a constant restated here.
    fill: Optional[int] = None
    #: The declared byte-emitting section order, verbatim. `check_budget_cursor`
    #: needs it to establish that a budget's cursor names a declared section head
    #: rather than an arbitrary label that happens to resolve.
    order: List[str] = []

    def region(self, name: str) -> Optional[MapRegion]:
        return next((r for r in self.regions if r.name == name), None)


def load_map(path: str) -> MapModel:
    """Read the game's declared ROM placement contract.

    map.toml is the placement AUTHORITY in this tree (CLAUDE.md, "the declared
    sigil map"), so the budgets come from there rather than from constants
    restated here. A malformed or budget-less map raises — silently reporting no
    budgets would recreate D7 one layer up.
    """
    with open(path, "rb") as f:
        doc = tomllib.load(f)

    regions = [
        MapRegion(name=r["name"], lma_base=r["lma_base"], size=r["size"],
                  kind=r.get("kind", ""))
        for r in doc.get("region", [])
    ]
    budgets = [
        MapBudget(region=b["region"], ceiling=b["ceiling"], cursor=b["cursor"])
        for b in doc.get("budget", [])
    ]
    if not regions:
        raise ListingFormatError(
            f"{path} declares no [[region]] — it is not a placement contract this "
            f"tool can read a budget out of.")
    fill = doc.get("fill")
    if fill is not None and not isinstance(fill, int):
        raise ListingFormatError(
            f"{path} declares `fill = {fill!r}`, which is not an integer byte — the "
            f"ROM-tail padding verdict is measured against it, so an unreadable fill "
            f"must stop the tool rather than fall back to a value nothing declared.")
    return MapModel(path=path, regions=regions, budgets=budgets, fill=fill,
                    order=list(doc.get("order", [])))


class BudgetRow(NamedTuple):
    region: str
    base: int
    cursor_name: str
    cursor_addr: int
    ceiling: int
    used: int
    limit: int

    @property
    def breached(self) -> bool:
        return self.cursor_addr > self.ceiling


def resolve_budgets(model: MapModel, listing: Listing) -> Tuple[List[BudgetRow], List[str]]:
    """Resolve each declared budget's cursor symbol against the listing.

    Returns (rows, unresolved). An UNRESOLVED cursor is reported by name, never
    dropped: a budget whose cursor symbol vanished from the build is precisely
    the case where "no row" and "0 bytes used" look the same.
    """
    rows: List[BudgetRow] = []
    unresolved: List[str] = []
    for b in model.budgets:
        region = model.region(b.region)
        if region is None:
            unresolved.append(f"{b.region} (no [[region]] of that name in {model.path})")
            continue
        addr = listing.by_name.get(b.cursor)
        if addr is None:
            unresolved.append(f"{b.region} (cursor symbol {b.cursor!r} not in the listing)")
            continue
        rows.append(BudgetRow(
            region=b.region, base=region.lma_base, cursor_name=b.cursor,
            cursor_addr=addr, ceiling=b.ceiling,
            used=addr - region.lma_base, limit=b.ceiling - region.lma_base,
        ))
    return rows, unresolved


class TailVerdict(NamedTuple):
    """How the bytes past `EndOfRom` are accounted for. `breach` is the only
    field the threshold reads; `line` is what the report prints either way."""
    kind: str            # 'exact' | 'appendix' | 'padding' | 'short' | 'unaccounted' | 'unmeasured'
    excess: Optional[int]
    line: str
    breach: Optional[str]


def classify_rom_tail(rom_path: Optional[str], rom_size: Optional[int],
                      endofrom: Optional[int], fill: Optional[int]) -> TailVerdict:
    """ACCOUNT for every byte between `EndOfRom` and the end of the ROM file.

    This replaces the un-failable `NOTE:` described in the module header (sigil's
    F4). `EndOfRom` standing in for the ROM file's size is a TERMINUS PROXY: the
    label is the end of the ASSEMBLED image, the file is that image plus whatever
    the pipeline appended, and the two are equal only by accident. Until now the
    difference printed as a note that named "padding, or a stale file" and could
    not fail, so a stale artifact, legitimate padding and real content placed past
    the image were one indistinguishable line — and under `--summary`, the flag
    build.sh uses, not even that.

    The direction that is never legitimate is `rom_size < endofrom`: the image on
    disk cannot be shorter than what the linker assembled. That is the refusal.
    The other direction is accounted rather than refused, because the excess IS
    legitimate on every shape this tree builds (the deb2 appendix), and a refusal
    that fires on a correct run is worse than the silence it replaces.

    `fill` is the map's declared byte, not a constant restated here; with no map,
    the padding branch says the fill it used was not declared.
    """
    if endofrom is None or rom_size is None:
        return TailVerdict("unmeasured", None,
                           "  EndOfRom  UNMEASURED — no EndOfRom symbol in the listing."
                           if endofrom is None else
                           "  EndOfRom  present, but the ROM file was not found — the "
                           "tail past the assembled image cannot be accounted for.",
                           None)

    excess = rom_size - endofrom
    if excess < 0:
        return TailVerdict(
            "short", excess,
            f"  EndOfRom  ${endofrom:06X} ({endofrom:,} B assembled) — the ROM FILE IS "
            f"SHORTER, by {-excess:,} B.",
            f"the ROM file {rom_path} is {rom_size:,} bytes but the listing assembles "
            f"{endofrom:,} bytes (EndOfRom ${endofrom:06X}) — the image on disk is "
            f"{-excess:,} bytes SHORT of what was linked. There is no legitimate cause: "
            f"it is a truncated write or a stale artifact from an earlier build. Do not "
            f"read any figure above as a measurement of this build.")

    head = f"  EndOfRom  ${endofrom:06X} ({endofrom:,} bytes assembled)"
    if excess == 0:
        return TailVerdict("exact", 0, head + " — the ROM file ends there exactly.", None)

    # The excess exists. Read it and say WHAT it is; every branch below names an
    # instrument rather than a guess.
    if rom_path is None or not os.path.isfile(rom_path):
        return TailVerdict(
            "unmeasured", excess,
            head + f"\n  TAIL UNMEASURED — {excess:,} B past the assembled image and no "
                   f"readable ROM at {rom_path!r} to classify them.",
            None)
    with open(rom_path, "rb") as f:
        f.seek(endofrom)
        tail = f.read()
    if len(tail) != excess:
        return TailVerdict(
            "unmeasured", excess,
            head + f"\n  TAIL UNMEASURED — asked for {excess:,} B past ${endofrom:06X} "
                   f"and read {len(tail):,}; the file changed under the tool.",
            None)

    if tail[:len(_DEB2_MAGIC)] == _DEB2_MAGIC:
        return TailVerdict(
            "appendix", excess,
            head + f"\n  tail ACCOUNTED: {excess:,} B at ${endofrom:06X} begin with the "
                   f"appendix magic {_DEB2_MAGIC.hex()} — the convsym deb2 symbol table "
                   f"sigil appends after the assembled image.",
            None)

    fill_byte = _DEFAULT_FILL if fill is None else fill
    provenance = "the map's declared `fill`" if fill is not None else \
                 "the built-in default (no --map given, so nothing declared one)"
    odd = next((i for i, b in enumerate(tail) if b != fill_byte), None)
    if odd is None:
        return TailVerdict(
            "padding", excess,
            head + f"\n  tail ACCOUNTED: {excess:,} B at ${endofrom:06X}, every one "
                   f"0x{fill_byte:02X} — padding, against {provenance}.",
            None)

    return TailVerdict(
        "unaccounted", excess,
        head + f"\n  tail UNACCOUNTED: {excess:,} B at ${endofrom:06X}.",
        f"{excess:,} bytes sit past EndOfRom (${endofrom:06X}) in {rom_path} and are "
        f"neither the deb2 symbol appendix (the first bytes are "
        f"{tail[:4].hex()}, not {_DEB2_MAGIC.hex()}) nor padding (first byte that is "
        f"not 0x{fill_byte:02X}, {provenance}, at file offset "
        f"${endofrom + odd:06X} = 0x{tail[odd]:02X}). Content placed after the "
        f"assembled image is invisible to every listing-reading gate in this tree, "
        f"and it BREAKS the MD Debugger: the vendored blob locates its symbol table "
        f"at the island's end, so anything between them makes every backtrace line "
        f"print <unknown> (games/sonic4/map.toml, THE FAULT-HANDLER ISLAND IS LAST).")


def check_budget_cursor(model: MapModel, row: BudgetRow) -> List[str]:
    """ASSERT what a budget's `cursor` label is standing in for (sigil's F3).

    `used = LMA(cursor) - region.lma_base` is a TERMINUS PROXY. The map spells the
    proxy out in its own words — the cursor is "the head-label of the first section
    PAST the object bank", the map-owned successor to the AS-era `if * > $20000`
    guard and the retired `__BUDGET_DATA` sentinel — so a REAL terminus was traded
    for a label, and nothing on either side of the seam checked the trade.

    ⚠ WHAT THIS FUNCTION CANNOT DO, stated here because a check whose limits are
    unwritten gets read as the whole answer. It cannot verify that the cursor is
    where the object bank ENDS. Nothing can, on the current contract: sigil's own
    `object_bank_cursor` says why — "the object bank and the data region share the
    [$10000,$20000) window and the data region extends BEYOND it, so an LMA window
    scan cannot separate them — only the declared boundary label can"
    (crates/sigil-harness/src/native.rs). Neither map.toml nor the listing declares
    which SECTIONS are bank content, so a section that is object code but is ordered
    AFTER the cursor makes `used` too small, the ceiling gate green over a real
    breach, and no instrument in either tree can see it. That gap needs a membership
    declaration in the map schema, which is a contract change; it is booked in
    docs/DEFERRED_WORK.md and is NOT closed here.

    What IS asserted, both of which were unchecked and neither of which is implied
    by the other:
      (a) the cursor resolves INSIDE the region it budgets. `used` is a subtraction
          with no floor: a cursor below `lma_base` yields a NEGATIVE used, which
          prints as a plausible small figure and passes `breached` (which only asks
          whether the cursor is past the ceiling).
      (b) the cursor NAMES A DECLARED SECTION HEAD — it must appear verbatim in the
          map's own `order` array, whose header defines that array as the
          byte-emitting section head-labels. `cursor = "..."` is a hand-edited
          string; nothing stopped it naming a mid-section label, which would
          measure a boundary the map never declared.
    """
    problems: List[str] = []
    region = model.region(row.region)
    region_end = row.base + region.size if region is not None else None

    if row.cursor_addr < row.base:
        problems.append(
            f"{row.region} cursor {row.cursor_name} resolves to ${row.cursor_addr:06X}, "
            f"BELOW the region base ${row.base:06X} — `used` would be "
            f"{row.used:,} bytes. The cursor is the head of the first section past the "
            f"region; a cursor below its base is not measuring that region at all.")
    elif region_end is not None and row.cursor_addr > region_end:
        # Distinct from `breached`: that compares against the declared CEILING,
        # which may sit below the region end. This says the proxy left the region.
        problems.append(
            f"{row.region} cursor {row.cursor_name} resolves to ${row.cursor_addr:06X}, "
            f"past the END of the region it budgets (${row.base:06X}+${region.size:X} = "
            f"${region_end:06X}). `used` = {row.used:,} B then counts bytes that are not "
            f"in the region.")

    if model.order and row.cursor_name not in model.order:
        problems.append(
            f"{row.region} cursor {row.cursor_name!r} is not a row of {model.path}'s "
            f"`order` array, which that file defines as the byte-emitting section "
            f"head-labels. The cursor is declared to be the HEAD of the first section "
            f"past the region; a label that is not a section head measures a boundary "
            f"nothing declared, and `used` is then a number about the wrong place. "
            f"Either point `cursor` at a section head listed in `order`, or add the "
            f"section this label heads to `order`.")
    return problems


# ---------------------------------------------------------------------------
# RAM layout
# ---------------------------------------------------------------------------

class RAMEntry(NamedTuple):
    name: str
    address: int
    size: int


class RAMLayout(NamedTuple):
    lower: List[RAMEntry]
    upper: List[RAMEntry]
    span_used: int            # highest symbol - $FFFF0000: what the map actually reaches
    free_before_stack: int
    stack_addr: int
    highest: int


_DEFAULT_STACK = 0xFFFFFF00
_RAM_TOTAL = 64 * 1024
_STACK_RE = re.compile(r'^\s*pub const SYSTEM_STACK\s*=\s*\$([0-9A-Fa-f]+)', re.MULTILINE)


def read_system_stack(repo_root: str = REPO_ROOT) -> Tuple[int, bool]:
    """SYSTEM_STACK from engine/system/constants.emp; (value, derived?).

    Read from the source of truth rather than restated, because a `pub const` is
    exactly the kind of value that moves once and leaves a stale copy behind in a
    tool. A sigil listing emits no constants at all, so the listing cannot supply
    it. Falls back to the documented $FFFFFF00 with `derived=False` so the caller
    can say which one it used.
    """
    src = os.path.join(repo_root, "engine", "system", "constants.emp")
    try:
        with open(src, "r") as f:
            m = _STACK_RE.search(f.read())
    except OSError:
        return _DEFAULT_STACK, False
    if not m:
        return _DEFAULT_STACK, False
    return int(m.group(1), 16), True


def _entries_from_sorted(syms: List[Tuple[str, int]], boundary: int) -> List[RAMEntry]:
    """Size each symbol by the gap to its successor (last one to `boundary`).

    Zero-size entries (two labels at one address, e.g. `Cheat_Flags` and
    `Engine_RAM_End`) are dropped rather than reported as real buffers.
    """
    entries: List[RAMEntry] = []
    for i, (name, addr) in enumerate(syms):
        size = syms[i + 1][1] - addr if i + 1 < len(syms) else boundary - addr
        if size > 0:
            entries.append(RAMEntry(name, addr, size))
    return entries


def compute_ram_layout(ram: Dict[str, int], stack_addr: int) -> Optional[RAMLayout]:
    """Per-buffer RAM breakdown. None when the listing carried no RAM symbols.

    None, not a zeroed layout: a build with no RAM labels is impossible, so the
    only thing a zeroed layout can mean is that the parse failed.
    """
    if not ram:
        return None

    lower_syms = sorted([(n, a) for n, a in ram.items() if a < _UPPER_RAM_START],
                        key=lambda x: x[1])
    upper_syms = sorted([(n, a) for n, a in ram.items() if a >= _UPPER_RAM_START],
                        key=lambda x: x[1])

    lower = _entries_from_sorted(lower_syms, _UPPER_RAM_START)
    # The last upper entry's true size is unknowable from labels alone, so it is
    # not extended to the stack; free_before_stack owns that gap.
    highest = max(a for a in ram.values())
    upper = _entries_from_sorted(upper_syms, highest)

    return RAMLayout(
        lower=lower, upper=upper,
        span_used=highest - _RAM_BASE,
        free_before_stack=stack_addr - highest,
        stack_addr=stack_addr, highest=highest,
    )


# ---------------------------------------------------------------------------
# VRAM layout — from the generated map, NOT from the listing
# ---------------------------------------------------------------------------

class VRAMRegion(NamedTuple):
    name: str
    base_tile: int
    tiles: int
    lifetime: str


class VRAMLayout(NamedTuple):
    source: str
    regions: List[VRAMRegion]
    total_tiles: int
    occupied_tiles: int        # UNION of the region ranges, not their sum
    free_tiles: int
    declared_free_tiles: int
    overlaps: List[str]


_VRAM_TOTAL_TILES = 2048       # 64 KB / 32 B per 4bpp 8x8 tile


def load_vram_layout(game: Optional[str]) -> Optional[VRAMLayout]:
    """VRAM allocation from `games/<game>/vram.toml`, the declared authority.

    A sigil listing emits no constants, so the old approach — scraping
    VRAM_PLANE_A / PLANE_H_CELLS out of the symbol table — has no input at all
    and reported nothing forever. vram.toml is already this tree's ONE VRAM
    authority (tools/vram_map.py is its generated mirror); read the source,
    because the mirror drops the `overlay_with` field this needs.

    Occupancy is the UNION of the tile ranges, never their sum. The sum is
    WRONG here and visibly so: `window_plane` deliberately aliases the tail of
    `plane_b` (the window feature is disabled), so adding tile counts reports
    2129 of 2048 tiles — 104% — for a map that is correct. A percentage over
    100 from an arithmetic mistake is worse than no percentage.

    Returns None when the file is absent; the caller says UNMEASURED.
    """
    if not game:
        return None
    path = os.path.join(REPO_ROOT, "games", game, "vram.toml")
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        doc = tomllib.load(f)

    raw = doc.get("region", [])
    regions = sorted(
        (VRAMRegion(name=r["name"], base_tile=r["base"], tiles=r["tiles"],
                    lifetime=r.get("lifetime", "")) for r in raw),
        key=lambda r: r.base_tile,
    )

    occupied: Set[int] = set()
    for r in regions:
        occupied.update(range(r.base_tile, r.base_tile + r.tiles))

    # Overlaps that vram.toml does NOT declare via overlay_with. Reported, not
    # gated: gen_vram_map owns enforcement, this is the dashboard saying what it
    # sees. Declared overlays are named so the row is not mistaken for a defect.
    declared_overlay = {r["name"]: set(r.get("overlay_with", [])) for r in raw}
    overlaps: List[str] = []
    for i, a in enumerate(regions):
        for b in regions[i + 1:]:
            if b.base_tile >= a.base_tile + a.tiles:
                continue
            pair = (f"{a.name} + {b.name}")
            if b.name in declared_overlay.get(a.name, ()) or \
               a.name in declared_overlay.get(b.name, ()):
                overlaps.append(f"{pair} (declared overlay)")
            else:
                overlaps.append(f"{pair} (UNDECLARED — no overlay_with)")

    declared_free = sum(f["tiles"] for f in doc.get("free", []))
    return VRAMLayout(
        source=f"games/{game}/vram.toml — NOT the listing (sigil emits no constants)",
        regions=regions, total_tiles=_VRAM_TOTAL_TILES,
        occupied_tiles=len(occupied),
        free_tiles=_VRAM_TOTAL_TILES - len(occupied),
        declared_free_tiles=declared_free,
        overlaps=overlaps,
    )


# ---------------------------------------------------------------------------
# Report formatters
# ---------------------------------------------------------------------------

def _fmt_size(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n / (1024*1024):.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n:,} B"


def _fmt_size_aligned(n: int, width: int = 10) -> str:
    return _fmt_size(n).rjust(width)


def format_rom_report(rom_size: Optional[int], rom_limit: int, endofrom: Optional[int],
                      budgets: List[BudgetRow], unresolved: List[str],
                      tail: Optional[TailVerdict] = None) -> str:
    lines = ["=== ROM Budget ==="]
    if rom_size is None:
        lines.append("ROM: UNMEASURED — the ROM binary was not found "
                     "(pass the path this build produced).")
    else:
        lines.append(f"ROM: {rom_size:,} / {rom_limit:,} bytes "
                     f"({rom_size / rom_limit * 100:.1f}%)  "
                     f"[{_fmt_size(rom_limit - rom_size)} free]")
    if tail is not None:
        lines.append(tail.line)
    elif endofrom is not None:
        lines.append(f"  EndOfRom  ${endofrom:06X} ({endofrom:,} bytes assembled)")
    else:
        lines.append("  EndOfRom  UNMEASURED — no EndOfRom symbol in the listing.")

    lines.append("")
    if budgets:
        lines.append("  Declared budgets (map.toml [[budget]], cursor resolved from the listing):")
        for b in budgets:
            pct = b.used / b.limit * 100 if b.limit else 0.0
            flag = "  ** OVER CEILING **" if b.breached else ""
            lines.append(
                f"    {b.region:<24} ${b.base:06X}-${b.cursor_addr:06X}  "
                f"{_fmt_size_aligned(b.used)} of {_fmt_size(b.limit)} ({pct:.1f}%){flag}")
            lines.append(f"      cursor {b.cursor_name} -> ${b.cursor_addr:06X}, "
                         f"ceiling ${b.ceiling:06X}")
    else:
        lines.append("  Declared budgets: NONE resolved.")
    for u in unresolved:
        lines.append(f"    UNMEASURED: {u}")
    return "\n".join(lines)


def format_ram_report(layout: Optional[RAMLayout], stack_derived: bool) -> str:
    lines = ["=== RAM Budget ==="]
    if layout is None:
        lines.append("RAM: UNMEASURED — the listing carried no symbols at $FFFF0000+. "
                     "That is impossible in a real build, so treat it as a parse failure, "
                     "not as an empty budget.")
        return "\n".join(lines)

    pct = layout.span_used / _RAM_TOTAL * 100
    lines.append(f"RAM: {layout.span_used:,} / {_RAM_TOTAL:,} bytes ({pct:.1f}%)  "
                 f"[{layout.free_before_stack:,} free before stack]")
    src = "engine/system/constants.emp" if stack_derived else "built-in fallback"
    lines.append(f"  top allocated ${layout.highest:08X}, "
                 f"stack ${layout.stack_addr:08X} (from {src})")
    lines.append("")

    if layout.lower:
        lines.append(f"  Lower RAM (${_RAM_BASE:08X}-${_UPPER_RAM_START - 1:08X}):")
        for e in layout.lower:
            lines.append(f"    {e.name:<34} {e.size:>10,} B")
        lines.append("")
    if layout.upper:
        lines.append(f"  Upper RAM (${_UPPER_RAM_START:08X}+) — 15 largest of "
                     f"{len(layout.upper)}:")
        for e in sorted(layout.upper, key=lambda x: -x.size)[:15]:
            lines.append(f"    {e.name:<34} {e.size:>10,} B  ${e.address:08X}")
        lines.append(f"    {'[Free]':<34} {layout.free_before_stack:>10,} B  "
                     f"-> ${layout.stack_addr:08X} (stack)")
    return "\n".join(lines)


def format_vram_report(layout: Optional[VRAMLayout]) -> str:
    lines = ["=== VRAM Budget ==="]
    if layout is None:
        lines.append("VRAM: UNMEASURED — a sigil listing emits no constants, and no "
                     "games/<game>/vram.toml was found for this build. Pass --map (or "
                     "--game) so this axis has an authority to read.")
        return "\n".join(lines)
    lines.append(f"VRAM: {layout.occupied_tiles:,} / {layout.total_tiles:,} tiles "
                 f"({layout.occupied_tiles / layout.total_tiles * 100:.1f}%)  "
                 f"[{layout.free_tiles:,} tiles free]")
    lines.append(f"  source: {layout.source}")
    if layout.declared_free_tiles != layout.free_tiles:
        lines.append(f"  WARNING: the map's [[free]] blocks total "
                     f"{layout.declared_free_tiles:,} tiles but {layout.free_tiles:,} "
                     f"are actually unoccupied — the free list has drifted from the "
                     f"regions.")
    for o in layout.overlaps:
        lines.append(f"  overlap: {o}")
    lines.append("")
    for r in layout.regions:
        end = r.base_tile + r.tiles - 1
        lines.append(f"  {r.name:<20} tiles {r.base_tile:>4}-{end:<4}  "
                     f"{r.tiles:>4} ({r.tiles * 32:>6,} B)  {r.lifetime}")
    return "\n".join(lines)


def format_summary(rom_size: Optional[int], rom_limit: int,
                   budgets: List[BudgetRow], unresolved: List[str],
                   ram: Optional[RAMLayout],
                   tail: Optional[TailVerdict] = None) -> str:
    """The build one-liner.

    UNMEASURED IS NOT ZERO — every axis here either carries a real number or
    says the word. `RAM: 0KB/64KB (0%)` read as a healthy measurement of an
    empty budget for months (D7); it can no longer be produced.

    THE TAIL AXIS IS HERE BECAUSE build.sh USES THIS FORM (2026-09-06, F4). The
    `EndOfRom` cross-check lived only in `format_rom_report`, which `--summary`
    never calls, so the one invocation that runs on every build could not print
    it. An axis the build cannot see is not a weaker check than one it can — it
    is a different artifact from the one the docs describe.
    """
    parts: List[str] = []
    if rom_size is None:
        parts.append("ROM: UNMEASURED (no ROM binary)")
    else:
        parts.append(f"ROM: {_fmt_size(rom_size)}/{_fmt_size(rom_limit)} "
                     f"({rom_size / rom_limit * 100:.1f}%)")
    if tail is not None:
        if tail.kind == "appendix":
            parts.append(f"tail: {_fmt_size(tail.excess)} deb2 appendix")
        elif tail.kind == "padding":
            parts.append(f"tail: {_fmt_size(tail.excess)} padding")
        elif tail.kind == "exact":
            parts.append("tail: none (file ends at EndOfRom)")
        elif tail.kind == "unmeasured":
            parts.append("tail: UNMEASURED")
        else:
            parts.append(f"tail: {tail.kind.upper()}")

    for b in budgets:
        pct = b.used / b.limit * 100 if b.limit else 0.0
        # `_fmt_size` and a fractional percent, NOT integer KB: a real 268-byte
        # object bank rendered as "0KB/64KB (0%)", which is character-for-character
        # the string D7 was about. A measured value must never print as zero.
        parts.append(f"{b.region}: {_fmt_size(b.used)}/{_fmt_size(b.limit)} ({pct:.1f}%)")
    for u in unresolved:
        parts.append(f"{u.split(' (')[0]}: UNMEASURED")

    if ram is None:
        parts.append("RAM: UNMEASURED (no ram symbols in the listing)")
    else:
        parts.append(f"RAM: {_fmt_size(ram.span_used)}/{_fmt_size(_RAM_TOTAL)} "
                     f"({ram.span_used / _RAM_TOTAL * 100:.1f}%)")
        parts.append(f"Free: {ram.free_before_stack / 1024:.1f}KB before stack")
    return " | ".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="s4budget",
        description="ROM/RAM/VRAM budget dashboard for the Aeon engine.",
    )
    p.add_argument("listing", help="Path to the sigil listing (s4.lst)")
    p.add_argument("rom", help="Path to the ROM binary (s4.bin)")
    p.add_argument("--map", dest="map_path", default=None,
                   help="games/<game>/map.toml — the declared placement contract "
                        "the [[budget]] rows come from. Without it the budget axis "
                        "is UNMEASURED (and says so).")
    p.add_argument("--game", default=None,
                   help="Game name, used to check tools/vram_map.py belongs to this "
                        "build. Inferred from --map when omitted.")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--summary", action="store_true",
                      help="Print compact one-liner to stderr (for build integration)")
    mode.add_argument("--json", action="store_true",
                      help="Output as JSON to stdout")
    p.add_argument("--rom-only", action="store_true", help="Show only ROM budget")
    p.add_argument("--ram-only", action="store_true", help="Show only RAM budget")
    p.add_argument("--vram-only", action="store_true", help="Show only VRAM budget")
    return p


def _infer_game(map_path: Optional[str]) -> Optional[str]:
    """`games/<game>/map.toml` -> `<game>`."""
    if not map_path:
        return None
    parts = os.path.normpath(map_path).split(os.sep)
    if len(parts) >= 2 and parts[-1] == "map.toml":
        return parts[-2]
    return None


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    if not os.path.isfile(args.listing):
        print(f"s4budget: error: listing file not found: {args.listing}", file=sys.stderr)
        return 1

    with open(args.listing, "r", encoding="utf-8", errors="replace") as f:
        listing_lines = f.readlines()

    try:
        listing = parse_listing(listing_lines)
    except ListingFormatError as e:
        # FATAL, not a warning. A listing this cannot read means every axis below
        # is fiction; the previous version of this tool answered the same
        # situation with zeros and a green exit (tools lens sweep D7).
        print(f"s4budget: cannot read {args.listing}: {e}", file=sys.stderr)
        return 1

    # The map is optional, but a map path that was GIVEN and cannot be read is an
    # error — a typo'd path must not silently downgrade the budget gate to a
    # warning, which is the shape of every gate this tree has caught going vacuous.
    model: Optional[MapModel] = None
    if args.map_path:
        if not os.path.isfile(args.map_path):
            print(f"s4budget: error: map file not found: {args.map_path}", file=sys.stderr)
            return 1
        try:
            model = load_map(args.map_path)
        except (ListingFormatError, tomllib.TOMLDecodeError, KeyError) as e:
            print(f"s4budget: error: cannot read {args.map_path}: {e}", file=sys.stderr)
            return 1

    game = args.game or _infer_game(args.map_path)

    rom_size = os.path.getsize(args.rom) if os.path.isfile(args.rom) else None
    rom_region = model.region("rom") if model else None
    rom_limit = rom_region.size if rom_region else 4 * 1024 * 1024
    endofrom = listing.by_name.get("EndOfRom")
    tail = classify_rom_tail(args.rom if os.path.isfile(args.rom) else None,
                             rom_size, endofrom, model.fill if model else None)

    if model:
        budgets, unresolved = resolve_budgets(model, listing)
    else:
        budgets, unresolved = [], ["budgets (no --map given; nothing declares a ceiling)"]
    cursor_problems: List[str] = []
    if model:
        for b in budgets:
            cursor_problems.extend(check_budget_cursor(model, b))

    stack_addr, stack_derived = read_system_stack()
    ram = compute_ram_layout(ram_labels(listing), stack_addr)
    vram = load_vram_layout(game)

    if args.json:
        print(json.dumps({
            "listing": {"symbols": listing.declared_count, "unused": listing.unused_count},
            "rom": {
                "size": rom_size, "limit": rom_limit, "endofrom": endofrom,
                "percent": round(rom_size / rom_limit * 100, 1) if rom_size else None,
                "budgets": [b._asdict() for b in budgets],
                "unmeasured": unresolved,
                "tail": tail._asdict(),
                "cursor_problems": cursor_problems,
            },
            "ram": None if ram is None else {
                "span_used": ram.span_used, "total": _RAM_TOTAL,
                "free_before_stack": ram.free_before_stack,
                "stack": ram.stack_addr,
                "lower": [e._asdict() for e in ram.lower],
                "upper": [e._asdict() for e in ram.upper],
            },
            "vram": None if vram is None else {
                "total_tiles": vram.total_tiles,
                "occupied_tiles": vram.occupied_tiles,
                "free_tiles": vram.free_tiles,
                "declared_free_tiles": vram.declared_free_tiles,
                "overlaps": vram.overlaps,
                "regions": [r._asdict() for r in vram.regions],
            },
        }, indent=2))
        return 0

    if args.summary:
        print(format_summary(rom_size, rom_limit, budgets, unresolved, ram, tail),
              file=sys.stderr)
    else:
        show_all = not (args.rom_only or args.ram_only or args.vram_only)
        sections = []
        if show_all or args.rom_only:
            sections.append(format_rom_report(rom_size, rom_limit, endofrom, budgets,
                                              unresolved, tail))
        if show_all or args.ram_only:
            sections.append(format_ram_report(ram, stack_derived))
        if show_all or args.vram_only:
            sections.append(format_vram_report(vram))
        print("\n\n".join(sections))

    # THE THRESHOLD. Until 2026-08-18 main() returned 0 on every path and the
    # limits were used ONLY to format percentages — this tool could print
    # "Object Bank ... 400.0% of 64 KB limit" and exit 0 (tools lens sweep D7).
    # Only MEASURED axes are gated; unmeasured ones are visible above and do not
    # fail, because hard-failing on an axis with no input is how a gate gets
    # re-wrapped in `|| true`, which is how this one was ignored to begin with.
    breaches = []
    if rom_size is not None and rom_size > rom_limit:
        breaches.append(f"ROM {rom_size:,} bytes exceeds the {rom_limit:,}-byte limit")
    for b in budgets:
        if b.breached:
            breaches.append(
                f"{b.region} cursor {b.cursor_name} at ${b.cursor_addr:06X} is past "
                f"its declared ceiling ${b.ceiling:06X} ({b.used:,} B used of "
                f"{b.limit:,} B)")
    if ram is not None and ram.free_before_stack <= 0:
        breaches.append(
            f"RAM top ${ram.highest:08X} has reached the stack at "
            f"${ram.stack_addr:08X} — {ram.free_before_stack:,} bytes free")
    # F4 — the ROM tail. `classify_rom_tail` decides; only the branches that cannot
    # have a legitimate cause carry a `breach` string, so ACCOUNTED tails (the deb2
    # appendix, declared padding) print above and change nothing here.
    if tail.breach:
        breaches.append(tail.breach)
    # F3 — the budget cursor proxy. A cursor that has stopped standing for the
    # region boundary makes `used` a number about the wrong place; that is not a
    # budget breach, but it is not a green either.
    breaches.extend(cursor_problems)
    if breaches:
        for b in breaches:
            print(f"s4budget: BUDGET EXCEEDED — {b}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
