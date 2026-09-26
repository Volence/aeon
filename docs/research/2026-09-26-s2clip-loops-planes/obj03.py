import struct
S2 = "/home/volence/sonic_hacks/s2disasm/level/objects/"
SIZES = [0x20, 0x40, 0x80, 0x100]


def load(z):
    d = open(f"{S2}{z}_1.bin", "rb").read()
    out = []
    for i in range(0, len(d) - 5, 6):
        x, yw, oid, st = struct.unpack(">HHBB", d[i:i + 6])
        if x == 0xFFFF:
            break
        out.append((x, yw & 0xFFF, (yw >> 13) & 1, (yw >> 14) & 1, oid, st))
    return out


def rows(z, w, h):
    objs = load(z)
    sw = [o for o in objs if o[4] == 3]
    res = []
    for x, y, xf, yf, oid, st in sw:
        horiz = bool(st & 4)
        hs = SIZES[st & 3]
        # crossing to the right (MainX) / downward (MainY): bit 3 path, bit 5 prio
        fwd = "B" if st & 8 else "A"
        back = "B" if st & 16 else "A"
        if xf:
            fwd = back = "keep"
        res.append(dict(x=x, y=y, st=st, horiz=horiz, half=hs, fwd=fwd,
                        fwd_hi=bool(st & 32), back=back, back_hi=bool(st & 64),
                        grounded=bool(st & 128), xflip=xf,
                        inside=(x < w and y < h)))
    return len(objs), res


if __name__ == "__main__":
    for z, w, h in (("EHZ", 10976, 1024), ("CPZ", 4576, 2048)):
        n, rs = rows(z, w, h)
        print(z, "objects", n, "Obj03", len(rs), "inside clip rect",
              sum(r["inside"] for r in rs))
        for r in rs:
            kind = "H-line" if r["horiz"] else "V-line"
            fdir = "down" if r["horiz"] else "right"
            bdir = "up" if r["horiz"] else "left"
            print(f"  {'IN ' if r['inside'] else 'out'} ({r['x']:5d},{r['y']:4d}) "
                  f"st=${r['st']:02X} {kind} half={r['half']:3d} "
                  f"{fdir}->{r['fwd']}{'/hi' if r['fwd_hi'] else ''} "
                  f"{bdir}->{r['back']}{'/hi' if r['back_hi'] else ''}"
                  f"{' grounded-only' if r['grounded'] else ''}")
