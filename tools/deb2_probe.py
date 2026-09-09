#!/usr/bin/env python3
"""Rebuild a ROM's deb2 symbol appendix from its `.lst`, so a symbol-set question
costs 0.1 s instead of a three-minute build.  A HAND INSTRUMENT, not a gate.

WHY IT EXISTS (LS-22a, 2026-09-07).  `build.sh` appends the `convsym` deb2 symbol
table into every shipped ROM, so an edit that changes only the SET OF SYMBOL NAMES
— a `mark`, a renamed label — moves ROM bytes.  Which of the four shapes it moves
is not derivable by argument: it depends on the Huffman code table the appendix
opens with, which is built from the CHARACTERS of every symbol name.  Answering
"would this name move this shape?" by building is 3 minutes a trial; this replays
the same pipeline over an existing listing in a tenth of a second, and `--verify`
proves it is the same pipeline by reproducing the ROM's own appendix byte for byte.

WHAT IT REPLAYS.  `sigil-harness`'s `append_deb2_appendix` drops equates, demangles
`$module$Parent$local` to `Parent.local`, re-emits the listing, and shells
`tools/convsym … -input as_lst -output deb2 -a`.  This does the same from the `.lst`
already on disk.  Verified 2026-09-07 at `0d64f534`: byte-identical to all four real
appendices (s4 `0xa773`, s4.debug `0xd5cd`, demo `0x6845`, demo.debug `0x80f7`), and
its prediction for `mark Sound_Dbg_Mirror_End` was byte-identical to what the real
mutated build put in `demo.debug.bin`.

DELIBERATELY NOT IN A BUILD LANE.  Its one checkable claim — the appendix in the ROM
is what convsym makes of the listing — is a claim about the pipeline that produced
both, so asserting it in the build would be the build grading its own output.  The
lane-run facts (the appendix is in the shipped image; a `mark` becomes a symbol) are
in `tools/test_deb2_appendix.py`.  This is for the next person asking a WHAT-IF.

WHAT IT DOES NOT DO.  It does not decode the appendix, does not tell you a ROM's CRC,
and models nothing below `EndOfRom`: the assembled image is the build's business.  It
also cannot see a symbol the listing does not carry.

    python3 tools/deb2_probe.py --verify
    python3 tools/deb2_probe.py --shape demo.debug --add-mark Sound_Dbg_Mirror_End
    python3 tools/deb2_probe.py --shape s4 --add-mark Foo_End --at Dynamic_Live
"""

import argparse
import os
import re
import struct
import subprocess
import sys
import tempfile

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONVSYM = os.path.join(AEON, "tools", "convsym")

#: The `-filter` build.sh passes verbatim; matches zero Aeon labels, kept for parity
#: with `sigil-harness`'s `CONVSYM_FILTER`.
FILTER = "z[A-Z].+"

SYMROW = re.compile(r"^([ *])(\S+) : ([0-9A-F]+) C \|$")
SHAPES = ("s4", "s4.debug", "demo", "demo.debug")


def read_symtab(lst_path):
    """[(name, value, unused)] from the listing's `Symbol Table` section, in order."""
    out, in_table = [], False
    with open(lst_path, errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("  Symbol Table"):
                in_table = True
                continue
            if not in_table:
                continue
            if line.strip().endswith("symbols"):
                break
            m = SYMROW.match(line)
            if m:
                out.append((m.group(2), int(m.group(3), 16), m.group(1) == "*"))
    return out


def _is_asm_block_scope(part):
    return part.startswith("asm") and len(part) > 3 and part[3:].isdigit()


def demangle(syms):
    """`sigil_link::demangle_symbols`: `$mod$Parent$local` -> `Parent.local`, and
    `__align$…` / any `asm<N>` scope dropped as compiler plumbing."""
    out = []
    for name, val, unused in syms:
        if "$" not in name:
            out.append((name, val, unused))
            continue
        parts = [p for p in name.split("$") if p]
        if (parts and parts[0] == "__align") or any(_is_asm_block_scope(p) for p in parts):
            continue
        if len(parts) >= 2:
            out.append(("%s.%s" % (parts[-2], parts[-1]), val, unused))
    return out


def emit_listing(syms):
    """`sigil_link::emit_listing`'s two address views. Sorted by (value, NAME) — the
    name is the tie-break, which is why a mark's position among same-address symbols
    is decided alphabetically."""
    rows = sorted(syms, key=lambda s: (s[1], s[0]))
    unused = sum(1 for s in rows if s[2])
    o = ["(0) %d/%X :        %s:\n" % (i + 1, s[1], s[0]) for i, s in enumerate(rows)]
    o.append("  Symbol Table (* = unused):\n")
    o.append("  --------------------------\n\n")
    o += ["%s%s : %X C |\n" % ("*" if s[2] else " ", s[0], s[1]) for s in rows]
    o.append("\n   %d symbols\n" % len(rows))
    o.append("    %d unused symbols\n" % unused)
    return "".join(o)


def deb2(syms):
    """The appendix bytes convsym packs for this symbol set."""
    if not os.path.isfile(CONVSYM):
        sys.exit("convsym not found at %s" % CONVSYM)
    d = tempfile.mkdtemp(prefix="deb2probe_")
    lst, blob = os.path.join(d, "r.lst"), os.path.join(d, "r.bin")
    with open(lst, "w") as fh:
        fh.write(emit_listing(syms))
    open(blob, "wb").close()          # empty, so the appendix starts at offset 0
    r = subprocess.run([CONVSYM, lst, blob, "-input", "as_lst",
                        "-range", "0", "FFFFFF", "-exclude", "-filter", FILTER, "-a"],
                       capture_output=True)
    if r.returncode != 0:
        sys.exit("convsym rc=%s: %s" % (r.returncode, r.stderr.decode()))
    with open(blob, "rb") as fh:
        out = fh.read()
    for f in (lst, blob):
        os.unlink(f)
    os.rmdir(d)
    return out


# --- appendix anatomy -------------------------------------------------------
# Derived by dissection 2026-09-08 (LS-22a-resid), then checked against all four
# built shapes: every bank block's entry array reproduces that bank's own symbol
# addresses in order, and the entry count the header implies equals the number of
# DISTINCT addresses in the bank.  Layout of the bytes convsym writes:
#
#   0x000  dc.w $DEB2, $0402          magic + version
#   0x004  256 x dc.l                 block pointer per address bits 23..16,
#                                     0 where the bank holds no symbol.  A block
#                                     pointer is (block start - 2).
#   0x404  N x <code:2><len:1><char:1> the Huffman code table over the CHARACTERS
#                                     of every name, ending at the lowest block
#                                     pointer + 2.  `char` 0 terminates a string.
#   block  dc.w ?, dc.l size          then (size-2)/4 entries of
#          <addr_low:2><str_off:2>    ascending address, then that block's packed
#                                     strings, `str_off` counted from their start.
#
# The one thing the appendix does NOT hold is a second name for an address: one
# record per address, so two symbols sharing an address cost one of them its name.
BLOCK_PTRS = slice(4, 0x404)
CODE_TABLE_START = 0x404


def anatomy(b):
    """(bank -> (block start, end), code table bytes) for one appendix."""
    idx = struct.unpack(">256I", b[BLOCK_PTRS])
    live = sorted((bank, ptr) for bank, ptr in enumerate(idx) if ptr)
    table = b[CODE_TABLE_START:live[0][1] + 2]
    blocks = {}
    for i, (bank, ptr) in enumerate(live):
        blocks[bank] = (ptr, live[i + 1][1] if i + 1 < len(live) else len(b))
    return blocks, table


def block_entries(b, ptr):
    """[(addr_low, string offset)] and the block's string area start."""
    size = struct.unpack(">H", b[ptr + 4:ptr + 6])[0]
    n = (size - 2) // 4
    ents = [struct.unpack(">HH", b[ptr + 6 + 4 * i:ptr + 6 + 4 * i + 4]) for i in range(n)]
    return ents, ptr + 6 + 4 * n


def decode_names(b):
    """{address: name} actually stored in the appendix.

    The strings are MSB-first bitstreams over the code table (`code` compared
    right-aligned against the bits read so far, char 0 ends the name).  Checked
    2026-09-08: every name this returns for all four shapes is a name the listing
    carries, and the count equals the listing's DISTINCT-address count."""
    blocks, table = anatomy(b)
    codes = {}
    for o in range(0, len(table), 4):
        code, ln, ch = struct.unpack(">HBB", table[o:o + 4])
        codes[(ln, code)] = ch
    out = {}
    for bank, (ptr, _end) in blocks.items():
        ents, strbase = block_entries(b, ptr)
        for low, off in ents:
            name, acc, ln, bit = bytearray(), 0, 0, 0
            while True:
                acc = (acc << 1) | ((b[strbase + off + (bit >> 3)] >> (7 - (bit & 7))) & 1)
                ln += 1
                bit += 1
                if (ln, acc) in codes:
                    ch = codes[(ln, acc)]
                    if ch == 0:
                        break
                    name.append(ch)
                    acc, ln = 0, 0
                if ln > 24:
                    raise ValueError("undecodable string in bank %02X at %#x" % (bank, off))
            out[(bank << 16) | low] = name.decode("latin-1")
    return out


def locate(b, off):
    """Which structure a byte offset falls in."""
    if off < CODE_TABLE_START:
        return "block-pointer index"
    blocks, table = anatomy(b)
    if off < CODE_TABLE_START + len(table):
        return "CODE TABLE"
    for bank, (start, end) in blocks.items():
        if start <= off < end:
            ents, strbase = block_entries(b, start)
            what = "entry %d of %d" % ((off - start - 6) // 4, len(ents)) \
                if off < strbase else "string area +%#x" % (off - strbase)
            return "bank %02X block, %s" % (bank, what)
    return "past the last block"


def compare(base, mut):
    """(identical, code table identical, first differing offset)."""
    first = next((i for i in range(min(len(base), len(mut))) if base[i] != mut[i]), None)
    if first is None and len(base) != len(mut):
        first = min(len(base), len(mut))
    return base == mut, anatomy(base)[1] == anatomy(mut)[1], first


def shape_files(shape):
    return os.path.join(AEON, shape + ".bin"), os.path.join(AEON, shape + ".lst")


def real_appendix(shape):
    """(appendix bytes, EndOfRom) out of the built ROM."""
    rom_path, lst_path = shape_files(shape)
    syms = dict((n, v) for n, v, _ in read_symtab(lst_path))
    eor = syms["EndOfRom"]
    with open(rom_path, "rb") as fh:
        rom = fh.read()
    return rom[eor:], eor


def cmd_verify(shapes):
    """The self-check: does this file reproduce what the build actually shipped?"""
    ok = True
    for shape in shapes:
        rom_path, lst_path = shape_files(shape)
        if not (os.path.isfile(rom_path) and os.path.isfile(lst_path)):
            print("%-11s SKIPPED — build it first (%s / %s absent)"
                  % (shape, os.path.basename(rom_path), os.path.basename(lst_path)))
            ok = False
            continue
        mine = deb2(demangle(read_symtab(lst_path)))
        real, eor = real_appendix(shape)
        same = mine == real
        ok &= same
        print("%-11s EndOfRom %#x  appendix %#x  %s"
              % (shape, eor, len(real), "IDENTICAL" if same else
                 "DIFFERENT (mine %#x)" % len(mine)))
    return 0 if ok else 1


def cmd_add(shape, name, anchor):
    rom_path, lst_path = shape_files(shape)
    if not os.path.isfile(lst_path):
        sys.exit("%s absent — build that shape first" % lst_path)
    syms = demangle(read_symtab(lst_path))
    hits = [v for n, v, _ in syms if n == anchor]
    if not hits:
        sys.exit("anchor %r is not a symbol in %s" % (anchor, os.path.basename(lst_path)))
    addr = hits[0]
    sharing = sorted(n for n, v, _ in syms if v == addr)
    base, mut = deb2(syms), deb2(syms + [(name, addr, False)])
    nd = sum(1 for a, b in zip(base, mut) if a != b) + abs(len(base) - len(mut))
    same, table_same, first = compare(base, mut)
    displaces = name < min(sharing)
    print("shape        %s" % shape)
    print("adding       %s @ %08X (an address already held by %s)" % (name, addr, sharing))
    print("appendix     %#x -> %#x (%+d bytes)" % (len(base), len(mut), len(mut) - len(base)))
    print("code table   %s" % ("UNCHANGED" if table_same else "CHANGED — a character's code moved"))
    print("displaces    %s — the appendix keeps ONE name per address, the lowest-sorting"
          % ("YES, %s loses its name to %s" % (min(sharing), name) if displaces else "no"))
    if same:
        print("VERDICT      this shape's ROM would NOT move for this name.")
        print("             It says nothing about the other three — measure them too.")
        return 0
    print("VERDICT      this shape's ROM WOULD MOVE: %d appendix bytes differ, first at "
          "%#x" % (nd, first))
    print("             (%s), plus the $18E header checksum. This is a byte-changing" % locate(base, first))
    print("             edit and owes the repin/refreeze ritual. Measure the other three.")
    return 0


def cmd_dissect(shape):
    lst_path = shape_files(shape)[1]
    if not os.path.isfile(lst_path):
        sys.exit("%s absent — build that shape first" % lst_path)
    syms = demangle(read_symtab(lst_path))
    b = deb2(syms)
    blocks, table = anatomy(b)
    print("%s appendix %#x bytes, code table %d characters (%#x..%#x)"
          % (shape, len(b), len(table) // 4, CODE_TABLE_START, CODE_TABLE_START + len(table)))
    for bank, (start, end) in sorted(blocks.items()):
        ents, strbase = block_entries(b, start)
        print("  bank %02X  %#08x..%#08x  %4d addresses, strings %#x..%#x (%d bytes)"
              % (bank, start, end, len(ents), strbase, end, end - strbase))
    stored = decode_names(b)
    listed = set(n for n, _, _ in syms)
    addrs = set(v & 0xFFFFFF for _, v, _ in syms)
    stray = sorted(n for n in stored.values() if n not in listed)
    print("  names decoded %d, listing distinct addresses %d, names the listing does not "
          "have: %d%s" % (len(stored), len(addrs), len(stray), (" " + str(stray[:5])) if stray else ""))
    dropped = sorted(set(listed) - set(stored.values()))
    print("  listing names the appendix does NOT store: %d%s"
          % (len(dropped), (" e.g. " + str(dropped[:5])) if dropped else ""))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--verify", action="store_true",
                    help="reproduce the built ROMs' own appendices and compare")
    ap.add_argument("--shape", choices=SHAPES,
                    help="the shape to probe (default: every one that is built)")
    ap.add_argument("--add-mark", metavar="NAME",
                    help="what-if: add this symbol and report whether the ROM moves")
    ap.add_argument("--at", metavar="SYMBOL", default="Dynamic_Live",
                    help="the symbol whose address the new one lands on — a `mark` "
                         "takes the address of the next var (default: Dynamic_Live)")
    ap.add_argument("--dissect", action="store_true",
                    help="print the appendix's own structure: code table and bank blocks")
    a = ap.parse_args(argv)
    shapes = [a.shape] if a.shape else list(SHAPES)
    if a.dissect:
        if not a.shape:
            ap.error("--dissect needs --shape")
        return cmd_dissect(a.shape)
    if a.add_mark:
        if not a.shape:
            ap.error("--add-mark needs --shape")
        return cmd_add(a.shape, a.add_mark, a.at)
    return cmd_verify(shapes)


if __name__ == "__main__":
    sys.exit(main())
