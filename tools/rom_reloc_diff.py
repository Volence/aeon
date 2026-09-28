#!/usr/bin/env python3
"""rom_reloc_diff — is a byte-moving ROM change a pure RELOCATION of its old content?

WHY THIS EXISTS (song bank 2, step 1, 2026-09-28). Moving the song pointer tables out of the
Moving-Trucks bank (ruling A: they go to their only reader, the 68k) shifts the SFX block and
the tables, so the ROM CRC changes and cannot be the check. This answers the question the CRC
used to answer: apart from where things now live, did any content change?

THE MODEL, derived from the two listings (nothing typed):
  * Every label both listings define is an anchor, once each listing ON ITS OWN is filtered to
    labels whose address rises in listing order and lies below EndOfRom (so phased
    `vma: $8000` heads and RAM labels, whose listing addresses are not ROM offsets, drop out;
    filtering each side separately keeps a section that was reordered past another). Anchor k
    maps old address a_k to new address b_k; the old bytes from a_k up to the next old anchor
    are "segment k", and they must reappear at b_k, byte for byte, for as long as BOTH sides
    still belong to segment k (up to the next anchor above it on each side; the old side's
    longer tail must be zero fill).
  * R(x) = x - a_k + b_k for the segment k holding old address x: the relocation function.
  * A differing byte is EXPLAINED only when it lies in a pointer cell whose old value is an
    address x and whose new value is R(x):
        - a big-endian 32-bit 68k absolute address (movea.l #SongTable, a SongTable entry,
          an SfxTable cell);
        - a 16-bit Z80 $8000-window pointer, big- or little-endian, whose old target
          (bank of the cell) relocates to a new target in the same bank.
    or when it is the header checksum word (0x18E) or the ROM-end long (0x1A4).
  * Everything at or past EndOfRom (the deb2 symbol appendix, which grows with new labels)
    is outside the comparison.
  * A new byte no old segment maps onto must be zero (fill or an explicit zero pad).

POSITIVE CHECK, the song tables: for each index i, the content SongTable[i] points at in the
old ROM equals the content it points at in the new ROM, for the length of the committed song
blob that matches it (games/sonic4/data/sound/song_*.bin; the SAME for SongPatchTable and the
*_patches.bin blobs). An entry whose content matches no committed blob is COULD NOT MEASURE.

Exit 0 a pure relocation · 1 unexplained differences (listed) · 2 could not measure.
Prints counts per explanation kind so a pass says what it accepted.

Usage:
    python3 tools/rom_reloc_diff.py --old OLD.bin --old-lst OLD.lst --new NEW.bin --new-lst NEW.lst
"""
from __future__ import annotations

import argparse
import bisect
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOUND_DIR = REPO / "games" / "sonic4" / "data" / "sound"

HEADER_CHECKSUM = (0x18E, 2)
HEADER_ROM_END = (0x1A4, 4)
WINDOW = 0x8000

_LABEL = re.compile(r"^\s*\(\d+\)\s+\d+/([0-9A-Fa-f]+)\s*:\s+([A-Za-z_$][\w.$]*):\s*$")


class CouldNotMeasure(Exception):
    pass


def listing_labels(path: Path) -> list[tuple[str, int]]:
    """(name, address) for every label line, in listing order, first definition wins."""
    seen: set[str] = set()
    out: list[tuple[str, int]] = []
    for line in path.read_text(errors="replace").splitlines():
        m = _LABEL.match(line)
        if m and m.group(2) not in seen:
            seen.add(m.group(2))
            out.append((m.group(2), int(m.group(1), 16)))
    return out


def end_of_rom(labels: list[tuple[str, int]], what: str) -> int:
    for name, addr in labels:
        if name == "EndOfRom":
            return addr
    raise CouldNotMeasure(f"{what}: the listing defines no EndOfRom")


def rom_labels(labels: list[tuple[str, int]], end: int) -> dict[str, int]:
    """Labels that are ROM offsets: below EndOfRom and rising in LISTING order. A phased
    (`vma: $8000`) head's labels list window addresses below the code that precedes them,
    and RAM labels list $FFxxxx; both drop out here."""
    out: dict[str, int] = {}
    last = -1
    for name, addr in labels:
        if addr < end and addr >= last:
            out[name] = addr
            last = addr
    return out


def anchors(old_l, new_l, old_end, new_end) -> list[tuple[str, int, int]]:
    """Labels that are ROM offsets in BOTH listings, sorted by old address. Each side is
    filtered on its own, so a section that moved past another (a reorder) keeps its anchor."""
    o, n = rom_labels(old_l, old_end), rom_labels(new_l, new_end)
    out = sorted(((name, a, n[name]) for name, a in o.items() if name in n), key=lambda x: x[1])
    if not out or out[0][1] != 0:
        raise CouldNotMeasure("no anchor at ROM offset 0 (the vector table); cannot segment")
    return out


class Reloc:
    def __init__(self, anc, old_end, new_end):
        self.a = [x[1] for x in anc]
        self.b = [x[2] for x in anc]
        self.names = [x[0] for x in anc]
        self.old_end, self.new_end = old_end, new_end

    def seg(self, x: int) -> int | None:
        if not 0 <= x < self.old_end:
            return None
        return bisect.bisect_right(self.a, x) - 1

    def __call__(self, x: int) -> int | None:
        k = self.seg(x)
        return None if k is None else x - self.a[k] + self.b[k]

    def spans(self):
        """(k, old_start, new_start, compared_len, old_len, new_len) per segment. The new
        span ends at the next NEW anchor above b_k (the new side may be reordered)."""
        n = len(self.a)
        bs = sorted(self.b)
        for k in range(n):
            old_len = (self.a[k + 1] if k + 1 < n else self.old_end) - self.a[k]
            j = bisect.bisect_right(bs, self.b[k])
            new_len = (bs[j] if j < len(bs) else self.new_end) - self.b[k]
            yield k, self.a[k], self.b[k], min(old_len, new_len), old_len, new_len


def _be32(buf, i):
    return int.from_bytes(buf[i:i + 4], "big") if i >= 0 and i + 4 <= len(buf) else None


def explain(old, new, pos_old, pos_new, R) -> tuple[str, int, int] | None:
    """Find a pointer cell covering this differing byte whose old value relocates to its new
    value. Returns (kind, cell_old_start, cell_len) or None."""
    delta = pos_new - pos_old
    for back in range(4):  # a 32-bit big-endian 68k absolute address
        o = pos_old - back
        ov, nv = _be32(old, o), _be32(new, o + delta)
        if ov is None or nv is None or ov == nv:
            continue
        if R(ov) == nv:
            return ("abs32", o, 4)
    for back in range(2):  # a 16-bit Z80 window pointer, either byte order
        o = pos_old - back
        if o < 0 or o + 2 > len(old) or o + delta + 2 > len(new):
            continue
        for order in ("big", "little"):
            ow = int.from_bytes(old[o:o + 2], order)
            nw = int.from_bytes(new[o + delta:o + delta + 2], order)
            if ow == nw or not (ow & WINDOW and nw & WINDOW):
                continue
            # the target lives in the bank of the cell's own section (the window it is read
            # through) — try that bank on the old side, and require the relocated target to
            # land at the new window offset in the new cell's bank.
            old_target = (o & ~(WINDOW - 1)) | (ow & (WINDOW - 1))
            new_target = R(old_target)
            if new_target is not None and (new_target & (WINDOW - 1)) == (nw & (WINDOW - 1)) \
                    and (new_target & ~(WINDOW - 1)) == ((o + delta) & ~(WINDOW - 1)):
                return (f"win16{order[0]}", o, 2)
    return None


def compare(old: bytes, old_lst: Path, new: bytes, new_lst: Path) -> dict:
    old_l, new_l = listing_labels(old_lst), listing_labels(new_lst)
    old_end, new_end = end_of_rom(old_l, "old"), end_of_rom(new_l, "new")
    if old_end > len(old) or new_end > len(new):
        raise CouldNotMeasure("EndOfRom lies past the ROM file (listing and ROM disagree)")
    anc = anchors(old_l, new_l, old_end, new_end)
    R = Reloc(anc, old_end, new_end)
    kinds: dict[str, int] = {}
    unexplained: list[str] = []
    header = {HEADER_CHECKSUM[0] + i for i in range(HEADER_CHECKSUM[1])} | \
             {HEADER_ROM_END[0] + i for i in range(HEADER_ROM_END[1])}
    covered_new = bytearray(new_end)
    moved = 0
    for k, a, b, n, old_len, new_len in R.spans():
        if a != b:
            moved += 1
        for i in range(n):
            covered_new[b + i] = 1
        i = 0
        while i < n:
            po, pn = a + i, b + i
            if old[po] == new[pn]:
                i += 1
                continue
            if po in header and pn == po:
                kinds["header"] = kinds.get("header", 0) + 1
                i += 1
                continue
            e = explain(old, new, po, pn, R)
            if e is None:
                unexplained.append(f"{po:#07x}->{pn:#07x} in segment {R.names[k]} "
                                   f"(+{po - a:#x}): {old[po]:02x} -> {new[pn]:02x}")
                i += 1
                continue
            kind, cell, ln = e
            kinds[kind] = kinds.get(kind, 0) + 1
            i = max(i + 1, cell + ln - a)
        for i in range(n, old_len):  # the longer old tail must be fill
            if old[a + i] != 0:
                unexplained.append(f"{a + i:#07x}: old byte {old[a + i]:02x} of segment "
                                   f"{R.names[k]} maps nowhere in the new ROM")
                break
    stray = [p for p in range(new_end) if not covered_new[p] and new[p] != 0]
    for p in stray[:20]:
        unexplained.append(f"new byte {p:#07x} = {new[p]:02x} is covered by no old segment")
    return {"anchors": len(anc), "moved_segments": moved, "kinds": kinds,
            "unexplained": unexplained, "stray_new": len(stray), "R": R,
            "old_labels": dict(old_l), "new_labels": dict(new_l)}


def committed_blobs() -> dict[str, bytes]:
    blobs = {}
    for p in sorted(SOUND_DIR.glob("*.bin")):
        if p.name.startswith("song_") or p.name.endswith("_patches.bin"):
            blobs[p.name] = p.read_bytes()
    if not blobs:
        raise CouldNotMeasure(f"no committed song/patch blobs under {SOUND_DIR}")
    return blobs


def table_entries(rom: bytes, labels: dict, name: str, count: int) -> list[int]:
    if name not in labels:
        raise CouldNotMeasure(f"the listing defines no {name}")
    base = labels[name]
    return [int.from_bytes(rom[base + 4 * i:base + 4 * i + 4], "big") for i in range(count)]


def song_count(labels: dict) -> int:
    st, spt = labels.get("SongTable"), labels.get("SongPatchTable")
    if st is None or spt is None or spt <= st or (spt - st) % 4:
        raise CouldNotMeasure("SongTable/SongPatchTable are not adjacent 4-byte arrays; "
                              "cannot derive SONG_COUNT from the listing")
    return (spt - st) // 4


def check_tables(old, new, res, blobs) -> tuple[list[str], list[str]]:
    """Each table entry's content is the same committed blob in both ROMs."""
    lines, bad = [], []
    ol, nl = res["old_labels"], res["new_labels"]
    n_old, n_new = song_count(ol), song_count(nl)
    if n_old != n_new:
        bad.append(f"SONG_COUNT changed: {n_old} -> {n_new}")
        return lines, bad
    for table in ("SongTable", "SongPatchTable"):
        oe, ne = table_entries(old, ol, table, n_old), table_entries(new, nl, table, n_new)
        for i, (op, np_) in enumerate(zip(oe, ne)):
            match = [nm for nm, bl in blobs.items()
                     if old[op:op + len(bl)] == bl and new[np_:np_ + len(bl)] == bl]
            if not match:
                old_m = [nm for nm, bl in blobs.items() if old[op:op + len(bl)] == bl]
                new_m = [nm for nm, bl in blobs.items() if new[np_:np_ + len(bl)] == bl]
                if not old_m and not new_m:
                    raise CouldNotMeasure(f"{table}[{i}] ({op:#x}/{np_:#x}) points at no "
                                          "committed blob in either ROM")
                bad.append(f"{table}[{i}]: old {op:#x} is {old_m or '?'}, new {np_:#x} is "
                           f"{new_m or '?'}")
                continue
            longest = max(match, key=lambda nm: len(blobs[nm]))
            lines.append(f"{table}[{i}] {longest} ({len(blobs[longest])} B): "
                         f"{op:#x} -> {np_:#x}")
    return lines, bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--old", required=True, type=Path)
    ap.add_argument("--old-lst", required=True, type=Path)
    ap.add_argument("--new", required=True, type=Path)
    ap.add_argument("--new-lst", required=True, type=Path)
    ap.add_argument("--no-tables", action="store_true",
                    help="skip the song-table check (a ROM with no sound bank)")
    args = ap.parse_args(argv)
    try:
        old, new = args.old.read_bytes(), args.new.read_bytes()
        res = compare(old, args.old_lst, new, args.new_lst)
        tl, tbad = ([], []) if args.no_tables else check_tables(old, new, res, committed_blobs())
    except (CouldNotMeasure, OSError) as e:
        print(f"rom_reloc_diff: COULD NOT MEASURE: {e}")
        return 2
    import zlib
    print(f"old {zlib.crc32(old):08x}/{len(old)}  new {zlib.crc32(new):08x}/{len(new)}")
    print(f"anchors {res['anchors']}, segments moved {res['moved_segments']}, "
          f"explained differences {res['kinds']}, stray new bytes {res['stray_new']}")
    for line in tl:
        print("  " + line)
    bad = res["unexplained"] + tbad
    if bad:
        print(f"FAIL: {len(bad)} unexplained difference(s):")
        for line in bad[:40]:
            print("  " + line)
        return 1
    print("PASS: every difference below EndOfRom is a relocation or a header word")
    return 0


if __name__ == "__main__":
    sys.exit(main())
