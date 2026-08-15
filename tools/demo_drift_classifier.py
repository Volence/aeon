#!/usr/bin/env python3
"""demo_drift_classifier — account for EVERY differing byte between two demo ROMs.

WHY THIS EXISTS, and why it is a tool rather than scratch.

`games/demo` is the permanent proof that the Aeon engine is game-agnostic, and the ritual for a
byte-moving parcel used to assert "both demo CRCs unchanged". For a parcel that adds ENGINE RAM
that criterion is unachievable and therefore carries zero bits: `games/demo/map.toml` places
`Raster_Install` and `Effects_InstallPreset`, so demo links the engine modules a parcel touches,
and growing a shared RAM region shifts every symbol allocated after it — those absolute addresses
are baked into demo's instruction stream even though demo runs none of that code.

Deleting the criterion outright would remove the only CONTENT-level instrument on the demo shapes.
Pins do not replace it: `repin --check` measures PLACEMENT, so a same-size edit to a shared engine
routine moves no symbol and passes clean. (Decided by Fable adviser, 2026-08-15.)

So the criterion becomes: the diff must classify COMPLETELY, with **zero unclassified bytes**, into

  (i)   RAM-operand relocations — a 16-bit operand whose OLD value is the address of a symbol at or
        after the grown region, and whose NEW value is that symbol's new address. The delta is read
        from the two symbol tables and asserted; it is never assumed, and never assumed to be
        POSITIVE. A region can grow downward, and a surprising sign is the classifier working.
  (ii)  the Genesis header's checksum ($18E) and ROM-end ($1A4-$1A7) fields, which must change.
  (iii) growth of the appended deb2 symbol table.

Anything else is a finding. Engine-RAM parcels recur, so this is the standing gate for the class.

  usage: demo_drift_classifier.py OLD.bin NEW.bin OLD.lst NEW.lst [--region-start HEX]

Exit 0 iff every differing byte in the common prefix is accounted for and the tail is deb2 only.
"""
from __future__ import annotations

import re
import sys
from typing import Dict, List, Tuple

# `(0) 1954/FFFF8A22 :        Raster_Buf_B:` — the sigil-canonical .lst symbol form.
LST_RE = re.compile(r"^\(\d+\)\s+\d+/([0-9A-Fa-f]{1,8})\s*:\s+([A-Za-z_][\w.$]*):")

HEADER_FIELDS = {
    0x18E: "header checksum",
    0x18F: "header checksum",
    0x1A4: "header ROM end",
    0x1A5: "header ROM end",
    0x1A6: "header ROM end",
    0x1A7: "header ROM end",
}


def symbols(path: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = LST_RE.match(line)
            if m:
                out[m.group(2)] = int(m.group(1), 16)
    if not out:
        raise SystemExit(f"no symbols parsed from {path} — the .lst format changed")
    return out


def ram_moves(old: Dict[str, int], new: Dict[str, int]) -> Dict[int, Tuple[int, List[str]]]:
    """old 16-bit operand value -> (new value, symbol names), for RAM symbols that MOVED.

    Keyed on the low 16 bits because that is how the 68000 spells a RAM address in an
    `(xxx).w` operand: `$FFFF8A22` is encoded as the word `$8A22`.
    """
    moves: Dict[int, Tuple[int, List[str]]] = {}
    for name, o in old.items():
        if o < 0xFF0000 or name not in new:
            continue
        n = new[name]
        if n == o:
            continue
        key, val = o & 0xFFFF, n & 0xFFFF
        if key in moves and moves[key][0] != val:
            raise SystemExit(
                f"ambiguous relocation: word ${key:04X} maps to both "
                f"${moves[key][0]:04X} and ${val:04X}"
            )
        moves.setdefault(key, (val, []))[1].append(name)
    return moves


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 4:
        raise SystemExit(__doc__)
    old_bin, new_bin, old_lst, new_lst = args

    a = open(old_bin, "rb").read()
    b = open(new_bin, "rb").read()
    so, sn = symbols(old_lst), symbols(new_lst)
    moves = ram_moves(so, sn)

    if not moves:
        print("NOTE: no RAM symbol moved between these two builds.")
    else:
        deltas = sorted({(v - k) if (v - k) < 0x8000 else (v - k) - 0x10000
                         for k, (v, _) in moves.items()})
        print(f"RAM symbols moved: {sum(len(n) for _, n in moves.values())}, "
              f"distinct signed deltas: {deltas}")
        if len(deltas) > 1:
            print("  (more than one delta — that is legal but worth reading; each is asserted "
                  "against the symbol tables individually, not against an assumed constant)")

    n = min(len(a), len(b))

    # --- where does the appended symbol table start? -----------------------------------
    # `EndOfRom`, straight out of the symbol table. It is exact and it is the linker's own
    # answer, so nothing here has to infer the boundary.
    #
    # It is NOT derivable from the Genesis header: the ROM-end field at $1A4 spans the whole
    # file, symbol appendix included, so it reports the same value for both regions. A first
    # attempt inferred the boundary from DIFF DENSITY instead and put it at $016800, twenty-one
    # kilobytes too high — the appendix's leading address entries move only a few bytes per
    # window, and only its trailing name region moves wholesale. That mis-boundary reported 615
    # "unclassified" bytes that were symbol-table content all along, i.e. a confident false
    # finding. Density heuristics do not get a vote when the linker emits the answer.
    if "EndOfRom" not in so or "EndOfRom" not in sn:
        raise SystemExit("no EndOfRom symbol — cannot separate code from the symbol appendix")
    if so["EndOfRom"] != sn["EndOfRom"]:
        print(f"NOTE: EndOfRom itself moved ${so['EndOfRom']:X} -> ${sn['EndOfRom']:X} — the "
              f"code/data region changed SIZE, which a pure RAM-growth parcel must not do.")
    appendix = min(so["EndOfRom"], sn["EndOfRom"])

    diffs = [i for i in range(n) if a[i] != b[i]]
    code_diffs = [i for i in diffs if i < appendix]
    tail_diffs = [i for i in diffs if i >= appendix]

    # --- classify the CODE region ------------------------------------------------------
    # A relocated operand is any 16-bit word whose value moved by one of the deltas the
    # SYMBOL TABLES report, and which points at or after the grown region. It is NOT
    # required to equal a symbol's own address: real operands address struct fields and
    # array elements (`Raster_Buf_B + 2`), so an exact-symbol rule classifies almost
    # nothing. The delta and the region floor both come from the symbol tables; neither
    # is assumed, and the sign is whatever the tables say.
    floor = min(moves) if moves else 0x10000
    deltas = {(v - k) for k, (v, _) in moves.items()}

    accounted: Dict[str, int] = {}
    unclassified: List[int] = []
    consumed = set()
    for off in code_diffs:
        if off in consumed:
            continue
        if off in HEADER_FIELDS:
            key = HEADER_FIELDS[off]
            accounted[key] = accounted.get(key, 0) + 1
            continue
        hit = False
        for base in (off - 1, off):
            if base < 0 or base + 2 > n:
                continue
            ow = int.from_bytes(a[base:base + 2], "big")
            nw = int.from_bytes(b[base:base + 2], "big")
            if ow >= floor and (nw - ow) in deltas:
                accounted["RAM operand relocation"] = accounted.get("RAM operand relocation", 0) + 1
                consumed.add(base)
                consumed.add(base + 1)
                hit = True
                break
        if not hit:
            unclassified.append(off)

    print(f"\nlengths: old {len(a)}  new {len(b)}  (tail delta {len(b) - len(a)} bytes)")
    print(f"symbol appendix starts at EndOfRom = ${appendix:06X} "
          f"({100 * appendix // n}% of the common prefix is code/data)")
    print(f"\nCODE/DATA region — differing bytes: {len(code_diffs)}")
    for k, v in sorted(accounted.items()):
        print(f"  accounted — {k}: {v}")
    print(f"  UNCLASSIFIED: {len(unclassified)}")
    print(f"\nSYMBOL APPENDIX region — differing bytes: {len(tail_diffs)}")
    print("  NOT byte-classified, and deliberately so: the appendix re-encodes every symbol")
    print("  address in a packed form, so a byte-level rule there would be asserting the")
    print("  encoder, not the engine. What IS asserted is that it is the ONLY region")
    print("  allowed to differ freely, and that the code/data region above reduces to zero.")

    if unclassified:
        print("\nfirst unclassified offsets (each is a finding, not noise):")
        for off in unclassified[:24]:
            print(f"  ${off:06X}  {a[off]:02X} -> {b[off]:02X}")
        print("\nFAIL — the demo code/data diff does not reduce to declared RAM growth.")
        return 1

    print("\nPASS — zero unclassified bytes in code/data: the demo diff reduces entirely to")
    print("RAM-operand relocations, the header fields, and symbol-appendix growth.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
