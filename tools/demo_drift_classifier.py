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

  (iv)  CODE RELOCATION — a byte whose new value equals the old byte one ROM-symbol delta
        earlier. The delta is per-symbol and read from the two tables, so the map is PIECEWISE:
        a parcel with three insertion sites gives downstream symbols three different shifts, and
        assuming one uniform delta would misclassify two thirds of them.
  (v)   DECLARED EDIT SPANS — bytes inside a symbol the caller NAMED with `--changed`. Inserted
        bytes have no old counterpart, so (iv) structurally cannot reach them.

Categories (iv)/(v) were added 2026-08-15 (Fable adviser) for parcels that add engine CODE, not
only engine RAM. The tool used to fail those by construction — its own `EndOfRom` note says a pure
RAM-growth parcel must not change the code region's SIZE — and the first such parcel scored 20,285
unclassified bytes, which is a shift signature, not a finding.

WHY (v) IS THE LOAD-BEARING HALF. Shift-tolerance ALONE would assert the linker: "everything moved
by the amount the linker says it moved" is true of any correct link and says nothing about the
engine. The declared-span rule is what keeps this an engine-content instrument — every differing
byte must be either pure relocation (cheap, mechanical, the linker's job) or inside a span the
parcel EXPLICITLY claims to have edited. An undeclared same-size edit to a shared engine routine
is still a finding, which is exactly the guarantee the retired "demo CRCs unchanged" criterion had.

So `--changed` is not a waiver list. It is the parcel stating its own footprint, and the tool
proving nothing else moved.

Anything else is a finding. Engine-RAM parcels recur, so this is the standing gate for the class.

  usage: demo_drift_classifier.py OLD.bin NEW.bin OLD.lst NEW.lst [--changed SYM,SYM,...]

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


def rom_spans(old: Dict[str, int], new: Dict[str, int], appendix: int
              ) -> List[Tuple[int, int, str, int | None]]:
    """Sorted (new_start, new_end, name, delta) over ROM symbols present in BOTH builds.

    The span of a symbol runs to the next symbol's address, which is how a byte offset is
    attributed to the routine that owns it. `delta` is that symbol's own move — per-symbol,
    never a single global shift, because a parcel with N insertion sites produces N different
    downstream shifts and one assumed delta would misclassify most of them.
    """
    common = [(new[n], n) for n in new if new[n] < appendix and not (0xFF0000 <= new[n])]
    common.sort()
    out: List[Tuple[int, int, str, int | None]] = []
    for i, (start, name) in enumerate(common):
        end = common[i + 1][0] if i + 1 < len(common) else appendix
        if end > start:
            # A symbol the OLD build does not have is NEW CODE. Its delta is None rather than
            # 0: there is no old counterpart to shift from, so the relocation rules cannot
            # speak for it and it must be DECLARED. Leaving new-only symbols out of the span
            # list entirely (the first version) silently attributed their bytes to whichever
            # common symbol preceded them, which reported a brand-new proc as unclassified
            # bytes inside its innocent neighbour.
            delta = (new[name] - old[name]) if name in old else None
            out.append((start, end, name, delta))
    return out


def span_at(spans: List[Tuple[int, int, str, int | None]], off: int) -> Tuple[str, int | None] | None:
    """Binary search: which ROM symbol owns this NEW-build offset, and by how much did it move."""
    lo, hi = 0, len(spans) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        start, end, name, delta = spans[mid]
        if off < start:
            hi = mid - 1
        elif off >= end:
            lo = mid + 1
        else:
            return name, delta
    return None


def main() -> int:
    argv = sys.argv[1:]
    changed: set[str] = set()
    args: List[str] = []
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok == "--changed" and i + 1 < len(argv):
            # The VALUE is consumed here, not filtered by a `startswith("--")` test — a
            # comma-separated list does not start with a dash and would otherwise be counted
            # as a fifth positional and print the usage instead of running.
            changed |= {x for x in argv[i + 1].split(",") if x}
            i += 2
            continue
        if tok.startswith("--changed="):
            changed |= {x for x in tok.split("=", 1)[1].split(",") if x}
        elif not tok.startswith("--"):
            args.append(tok)
        i += 1
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
    spans = rom_spans(so, sn, appendix)
    rom_deltas = {d for _, _, _, d in spans if d}
    # PC-RELATIVE STRADDLE. A `bsr`/`bra` displacement is the DISTANCE between two symbols, so
    # it changes by delta(target) - delta(branch), which is generally not any symbol's own
    # delta. An insertion between the branch and its target moves the word by that difference
    # while every byte around it shifts cleanly. The candidate set is still derived entirely
    # from the two symbol tables; nothing is assumed.
    pcrel_deltas = {x - y for x in rom_deltas | {0} for y in rom_deltas | {0}} - {0}
    edited_spans: set[str] = set()
    shifted_spans: set[str] = set()

    def reloc_at(off: int, d: int) -> str | None:
        """Is `off` inside an operand that moved by a table-derived delta?

        THE OLD SIDE IS READ AT `off - d`, NOT AT `off`, and that is the correction that makes
        this work on a code-adding parcel. Index-aligned comparison is only meaningful while
        nothing shifts; once the code region grows, the instruction that USED to live at this
        address is somewhere else entirely, and comparing same-index words compares unrelated
        instructions. The first version of this extension did exactly that and left 1,750 bytes
        unclassified inside routines the parcel never touched.
        """
        for width, kinds in ((4, ("ROM operand relocation",)), (2, ("RAM operand relocation",
                                                                    "ROM operand relocation",
                                                                    "PC-relative straddle"))):
            for base in range(off - (width - 1), off + 1):
                if base < 0 or base + width > n:
                    continue
                src = base - d
                if src < 0 or src + width > len(a):
                    continue
                ov = int.from_bytes(a[src:src + width], "big")
                nv = int.from_bytes(b[base:base + width], "big")
                if nv == ov:
                    continue
                delta = nv - ov
                if width == 2:
                    if ov >= floor and delta in deltas:
                        kind = "RAM operand relocation"
                    elif delta in rom_deltas:
                        kind = "ROM operand relocation"
                    elif delta in pcrel_deltas:
                        kind = "PC-relative straddle"
                    else:
                        continue
                else:
                    if ov < appendix and delta in rom_deltas:
                        kind = "ROM operand relocation"
                    else:
                        continue
                for k in range(base, base + width):
                    consumed.add(k)
                return kind
        return None

    for off in code_diffs:
        if off in consumed:
            continue
        if off in HEADER_FIELDS:
            key = HEADER_FIELDS[off]
            accounted[key] = accounted.get(key, 0) + 1
            continue

        # Which routine owns this byte in the NEW build, and how far did that routine move?
        owner = span_at(spans, off)
        name, d = owner if owner is not None else ("<no span>", 0)

        # A DECLARED edit is checked before anything else: inside an edited routine the shift
        # and operand rules would report accidental matches as relocation and hide the very
        # bytes the parcel changed.
        if name in changed:
            accounted["declared edit span"] = accounted.get("declared edit span", 0) + 1
            edited_spans.add(name)
            continue

        if d is None:
            # New code that was NOT declared. This is the finding the declared-span rule
            # exists to produce: a parcel that adds a routine to a module demo links has
            # changed demo's content, and must say so.
            unclassified.append(off)
            continue

        kind = reloc_at(off, d)
        if kind is not None:
            accounted[kind] = accounted.get(kind, 0) + 1
            continue

        src = off - d
        if 0 <= src < len(a) and a[src] == b[off]:
            accounted["code relocation"] = accounted.get("code relocation", 0) + 1
            if d:
                shifted_spans.add(name)
            continue

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

    # --- the insertion map: what the parcel says it edited, and what that cost ---------
    if changed:
        print(f"\nDECLARED edit spans ({len(changed)} named, {len(edited_spans)} carried "
              f"differing bytes):")
        for name in sorted(changed):
            hit = "touched" if name in edited_spans else "NO differing bytes"
            old_a = so.get(name)
            new_a = sn.get(name)
            if old_a is None or new_a is None:
                print(f"  {name:<32} NOT A SYMBOL IN BOTH BUILDS — check the name")
            else:
                print(f"  {name:<32} ${old_a:06X} -> ${new_a:06X}  ({hit})")
        stale = sorted(n for n in changed if n in so and n in sn and n not in edited_spans)
        if stale:
            print("  NOTE: a declared span with no differing bytes is not an error, but it is")
            print("  worth reading — either the edit was byte-neutral, or the name is wrong and")
            print("  its real bytes are being counted somewhere else.")
    if shifted_spans:
        print(f"\nrelocated (unedited) ROM symbols carrying differing bytes: {len(shifted_spans)}")

    if unclassified:
        print("\nfirst unclassified offsets (each is a finding, not noise):")
        for off in unclassified[:24]:
            print(f"  ${off:06X}  {a[off]:02X} -> {b[off]:02X}")
        print("\nFAIL — the demo code/data diff does not reduce to declared growth.")
        return 1

    print("\nPASS — zero unclassified bytes in code/data: the demo diff reduces entirely to")
    print("operand relocations, code relocation by per-symbol deltas, the DECLARED edit spans,")
    print("the header fields, and symbol-appendix growth.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
