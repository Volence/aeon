#!/usr/bin/env python3
"""stub_rom — write a scratch ROM copy with named routines' first word replaced by `rts`.

A PROBE, never a fix (the S2CLIP-LAG study's prefetch-stub method, generalised): removing
a routine's whole cost and re-running a leg gives the UPPER BOUND of what any optimisation
of that routine could buy on that leg, in lag frames. It changes behaviour (a stubbed
parallax stops scrolling, a stubbed audit stops auditing), so it answers "how much lag is
this routine worth", never "is the game still right".

Addresses come from the build's own .lst (`(0) line/ADDR :   Name:` rows); a name that is
not found, or found twice at different addresses, is REFUSED. The original first word is
printed so the edit is on the record.

Usage: stub_rom.py <in.bin> <in.lst> <out.bin> NAME[=HEXBYTES] [...]
  NAME alone writes `rts` (4e75). NAME=HEXBYTES writes those bytes at the entry instead:
  a hand-assembled replacement body (e.g. a plain copy loop in place of a translating
  one), to price a cheaper IMPLEMENTATION rather than none. The replacement must fit
  before the next listed label; that is checked against the .lst and refused otherwise.
"""
import re
import sys
import zlib
from pathlib import Path

ROW = re.compile(r"^\(\d+\)\s+\d+/([0-9A-Fa-f]+)\s*:\s+([A-Za-z_$][\w$.]*):\s*$")


def main():
    src, lst, out, specs = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
    bodies = {}
    for sp in specs:
        n, _, hx = sp.partition("=")
        bodies[n] = bytes.fromhex(hx) if hx else b"\x4e\x75"
    names = list(bodies)
    all_addrs = []
    if not names:
        raise SystemExit("stub_rom: name at least one routine")
    found = {}
    for line in Path(lst).read_text(errors="replace").splitlines():
        m = ROW.match(line)
        if m:
            all_addrs.append(int(m.group(1), 16))
        if m and m.group(2) in names:
            found.setdefault(m.group(2), set()).add(int(m.group(1), 16))
    rom = bytearray(Path(src).read_bytes())
    for n in names:
        addrs = found.get(n)
        if not addrs or len(addrs) != 1:
            raise SystemExit(f"stub_rom: REFUSED {n}: addresses {sorted(addrs or [])} in {lst}")
        a = next(iter(addrs))
        body = bodies[n]
        nxt = min((x for x in all_addrs if x > a), default=None)
        if nxt is not None and a + len(body) > nxt:
            raise SystemExit(f"stub_rom: REFUSED {n}: {len(body)}-byte body overruns the next label at ${nxt:06X}")
        was = rom[a:a + len(body)].hex()
        rom[a:a + len(body)] = body
        print(f"stub {n} @ ${a:06X}: {was} -> {body.hex()}")
    Path(out).write_bytes(rom)
    print(f"{src} crc {zlib.crc32(Path(src).read_bytes()):08x} -> {out} crc {zlib.crc32(rom):08x} "
          f"size {len(rom)}")


if __name__ == "__main__":
    main()
