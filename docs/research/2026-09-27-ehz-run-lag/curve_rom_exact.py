#!/usr/bin/env python3
"""curve_rom_exact.py <rom> <lst> [--ref <rom> <lst>] [--sample N] [--seed S]

COPIED 2026-09-27 (perf/ehz-run-lag) from docs/research/2026-09-25-ehz-diag-regression/, with
the interpreter extended by exactly the opcodes the packed, 8x-unrolled `.lp_curve` uses and
the one-line loop did not: `andi.w #imm,Dn`, `lsr.w #imm,Dn` and `move.l Dn,(An)+` (written as
two word stores, high word first, the 68000's big-endian order). Everything else, the
anchors, the cases and the expectation, is the original's; the original is left as it was.

THE EXHAUSTIVE CURVE CHECK, RUN ON THE BUILT MACHINE CODE rather than on a Python model of it.
`curve_exact.py` (the research parcel's check) models the prototype's arithmetic; it cannot see
what sigil actually emitted. This tool pulls the two curve blocks OUT OF THE ROM IMAGE -- the
tail of the hoist from `ext.l d2 / divs.w d4,d2` down to `.curve_next`, and the fill's curve
block from the entry-length setup through the loop to the carry park -- and interprets those
bytes with a small 68000 interpreter that knows exactly the opcodes those two blocks use (an
unknown opcode is a hard stop, never a skip).

For each case it seeds the registers the way the engine does at those two points (d2 = spread,
d4 = span for the hoist; the record words the hoist just wrote, d1 = acc seed, d6 = 0, a4 = the
buffer for the loop) and reads back every BG word the loop wrote. The expectation is the EXACT
ramp, computed here: word(k) = base + floor(k * spread / span), mod 65536. That is what the
shipped Bresenham loop computes (err in [0, span), one-directional correction on a floor-
normalised remainder); `--ref` interprets a second ROM (today's master) against the same
expectation, so "the expectation is the shipped behaviour" is measured, not asserted.

CASES
  exhaustive : span 1..224, rem 0..span-1, for step 0 (spread = rem) and step -1
               (spread = rem - span: the negative-spread path through the floor fixup),
               224 lines each (stricter than any real layer: a layer emits <= span lines).
  split      : --sample random (spread in -32768..32767, span, base, a split line), run as
               TWO entries: the parent up to the split, the carry parked, the CONT entry
               resumed from the park -- the anchored-overlay continuation.
Exit 0 = zero mismatches in every family; 1 = a mismatch; 2 = could not run.
"""
import random
import re
import sys
import zlib

M16 = 0xFFFF
M32 = 0xFFFFFFFF


def s16(v):
    v &= M16
    return v - 0x10000 if v & 0x8000 else v


def s32(v):
    v &= M32
    return v - 0x100000000 if v & 0x80000000 else v


class Stop(Exception):
    pass


class CPU:
    """Just the opcodes the two curve blocks use. Word-sized ops keep the high word."""

    def __init__(self, rom):
        self.rom = rom
        self.d = [0] * 8
        self.a = [0] * 8
        self.x = self.n = self.z = self.v = self.c = 0
        self.mem = {}                  # word writes: addr -> u16

    def w(self, pc):
        return (self.rom[pc] << 8) | self.rom[pc + 1]

    def setw(self, r, val):
        self.d[r] = (self.d[r] & 0xFFFF0000) | (val & M16)

    def nz16(self, r):
        self.n = 1 if r & 0x8000 else 0
        self.z = 1 if (r & M16) == 0 else 0

    def run(self, pc, stop_pc, max_steps=10_000):
        for _ in range(max_steps):
            if pc == stop_pc:
                return
            pc = self.step(pc)
        raise Stop(f"no stop after {max_steps} steps")

    def bcc(self, pc, op, cond):
        disp = op & 0xFF
        if disp == 0:
            d = s16(self.w(pc + 2)); nxt = pc + 4; tgt = pc + 2 + d
        else:
            d = disp - 0x100 if disp & 0x80 else disp; nxt = pc + 2; tgt = pc + 2 + d
        return tgt if cond else nxt

    def step(self, pc):
        op = self.w(pc)
        hi4 = op >> 12
        dn = (op >> 9) & 7
        rn = op & 7
        mode = (op >> 3) & 7
        # ---- ext.l Dn ----
        if op & 0xFFF8 == 0x48C0:
            v = s16(self.d[rn]) & M32; self.d[rn] = v
            self.n = v >> 31; self.z = int(v == 0); self.v = self.c = 0
            return pc + 2
        # ---- swap Dn ----
        if op & 0xFFF8 == 0x4840:
            v = self.d[rn]; v = ((v << 16) | (v >> 16)) & M32; self.d[rn] = v
            self.n = v >> 31; self.z = int(v == 0); self.v = self.c = 0
            return pc + 2
        # ---- tst.w Dn ----
        if op & 0xFFF8 == 0x4A40:
            self.nz16(self.d[rn]); self.v = self.c = 0
            return pc + 2
        # ---- clr.w Dn ----
        if op & 0xFFF8 == 0x4240:
            self.setw(rn, 0); self.n = 0; self.z = 1; self.v = self.c = 0
            return pc + 2
        # ---- andi.w #imm,Dn ----
        if op & 0xFFF8 == 0x0240:
            r = self.d[rn] & self.w(pc + 2)
            self.setw(rn, r); self.nz16(r); self.v = self.c = 0
            return pc + 4
        # ---- lsr.w #q,Dn (immediate count, register form) ----
        if op & 0xF1F8 == 0xE048:
            q = dn or 8
            a = self.d[rn] & M16
            r = a >> q
            self.c = self.x = (a >> (q - 1)) & 1
            self.setw(rn, r); self.nz16(r); self.v = 0
            return pc + 2
        # ---- move.l Dn,(An)+ ----
        if op & 0xF1F8 == 0x20C0:
            v = self.d[rn] & M32
            self.mem[self.a[dn]] = v >> 16
            self.mem[(self.a[dn] + 2) & M32] = v & M16
            self.a[dn] = (self.a[dn] + 4) & M32
            self.n = v >> 31; self.z = int(v == 0); self.v = self.c = 0
            return pc + 2
        # ---- nop ----
        if op == 0x4E71:
            return pc + 2
        # ---- divs.w / divu.w Dn,Dm ----
        if op & 0xF1F8 == 0x81C0 or op & 0xF1F8 == 0x80C0:
            signed = op & 0x0100
            src = self.d[rn] & M16
            if src == 0:
                raise Stop(f"divide by zero at {pc:#x}")
            dvd = self.d[dn]
            if signed:
                a, b = s32(dvd), s16(src)
                q = abs(a) // abs(b)
                if (a < 0) != (b < 0):
                    q = -q
                r = a - q * b
                if not -0x8000 <= q <= 0x7FFF:
                    raise Stop(f"divs overflow at {pc:#x}")
            else:
                q, r = dvd // src, dvd % src
                if q > 0xFFFF:
                    raise Stop(f"divu overflow at {pc:#x}")
            self.d[dn] = ((r & M16) << 16) | (q & M16)
            self.nz16(q); self.v = self.c = 0
            return pc + 2
        # ---- move.w Dn,Dm / move.w Dn,d16(An) / move.w d16(An),Dn / move.w Dn,(An)+ ----
        if hi4 == 3:
            dmode = (op >> 6) & 7
            if mode == 0:
                val = self.d[rn] & M16; nxt = pc + 2
            elif mode == 5:
                addr = (self.a[rn] + s16(self.w(pc + 2))) & M32
                val = self.mem.get(addr, 0); nxt = pc + 4
            else:
                raise Stop(f"move.w source mode {mode} at {pc:#x}")
            if dmode == 0:
                self.setw(dn, val)
            elif dmode == 5:
                addr = (self.a[dn] + s16(self.w(nxt))) & M32; nxt += 2
                self.mem[addr] = val
            elif dmode == 3:
                self.mem[self.a[dn]] = val; self.a[dn] = (self.a[dn] + 2) & M32
            else:
                raise Stop(f"move.w dest mode {dmode} at {pc:#x}")
            self.nz16(val); self.v = self.c = 0
            return nxt
        # ---- movea.l An,Am ----
        if op & 0xF1F8 == 0x2048:
            self.a[dn] = self.a[rn]
            return pc + 2
        # ---- add.w / sub.w / cmp.w Dn,Dm ; addx.w Dn,Dm ; adda.w Dn,Am ; cmpa.l An,Am ----
        if op & 0xF1F8 == 0xD140:                                 # addx.w Dn,Dm
            a, b = self.d[dn] & M16, self.d[rn] & M16
            r = a + b + self.x
            self.setw(dn, r)
            self.c = self.x = int(r > M16)
            if r & M16:
                self.z = 0
            self.n = (r >> 15) & 1
            return pc + 2
        if op & 0xF1F8 == 0xD040 or op & 0xF1F8 == 0x9040 or op & 0xF1F8 == 0xB040:
            if mode != 0:
                raise Stop(f"add/sub/cmp mode {mode} at {pc:#x}")
            a, b = self.d[dn] & M16, self.d[rn] & M16
            kind = op & 0xF000
            if kind == 0xD000:
                r = a + b; carry = int(r > M16)
                self.v = int(((a ^ r) & (b ^ r) & 0x8000) != 0)
            else:
                r = a - b; carry = int(r < 0)
                self.v = int(((a ^ b) & (a ^ r) & 0x8000) != 0)
            self.nz16(r); self.c = carry
            if kind != 0xB000:
                self.x = carry; self.setw(dn, r)
            return pc + 2
        if op & 0xF1F8 == 0xD0C0:                                 # adda.w Dn,Am
            self.a[dn] = (self.a[dn] + s16(self.d[rn])) & M32
            return pc + 2
        if op & 0xF1F8 == 0xB1C8:                                 # cmpa.l An,Am
            a, b = self.a[dn], self.a[rn]
            r = a - b
            self.c = int(r < 0); r &= M32
            self.z = int(r == 0); self.n = r >> 31
            return pc + 2
        # ---- addq.w / subq.w #q,Dn ----
        if op & 0xF1F8 in (0x5040, 0x5140) and mode == 0:
            q = dn or 8
            a = self.d[rn] & M16
            if op & 0x0100:
                r = a - q; carry = int(r < 0)
            else:
                r = a + q; carry = int(r > M16)
            self.setw(rn, r); self.nz16(r); self.c = self.x = carry
            return pc + 2
        # ---- dbf Dn ----
        if op & 0xFFF8 == 0x51C8:
            cnt = (self.d[rn] - 1) & M16
            self.setw(rn, cnt)
            if cnt == M16:
                return pc + 4
            return pc + 2 + s16(self.w(pc + 2))
        # ---- Bcc ----
        if hi4 == 6:
            cc = (op >> 8) & 0xF
            cond = {0x0: True, 0x4: not self.c, 0x5: bool(self.c),
                    0xC: (self.n ^ self.v) == 0, 0xD: (self.n ^ self.v) == 1,
                    0x7: bool(self.z), 0x6: not self.z}.get(cc)
            if cond is None:
                raise Stop(f"Bcc {cc:#x} at {pc:#x}")
            return self.bcc(pc, op, cond)
        raise Stop(f"unknown opcode {op:04x} at {pc:#x}")


def lst_symbols(lst):
    sym = {}
    pat = re.compile(r"^\s*\(\d+\)\s+\d+/([0-9A-Fa-f]+)\s*:\s*(\S+):\s*$")
    for line in open(lst, errors="replace"):
        m = pat.match(line)
        if m:
            sym[m.group(2)] = int(m.group(1), 16)
    return sym


def find_one(rom, pat, lo, hi, what):
    i = rom.find(pat, lo, hi)
    if i < 0 or rom.find(pat, i + 1, hi) >= 0:
        raise Stop(f"{what}: pattern {pat.hex()} not unique in [{lo:#x},{hi:#x})")
    return i


class Blocks:
    """Locate the two blocks in one ROM by its own listing's bracket labels."""

    def __init__(self, rom_path, lst_path):
        self.rom = open(rom_path, "rb").read()
        self.name = rom_path.split("/")[-1]
        self.crc = zlib.crc32(self.rom)
        sym = lst_symbols(lst_path)

        def lab(tail):
            hits = [v for k, v in sym.items() if k.endswith(tail)]
            if len(hits) != 1:
                raise Stop(f"{self.name}: label *{tail} found {len(hits)} times")
            return hits[0]
        h0, h1 = lab("cap_factor_curve_hoist_begin"), lab("cap_factor_curve_hoist_end")
        b0, b1 = lab("cap_factor_curve_band_begin"), lab("cap_factor_curve_band_end")
        # hoist: from `ext.l d2 ; divs.w d4,d2` to the `adda.w #imm,a1` that opens .curve_next
        self.h_start = find_one(self.rom, bytes.fromhex("48C285C4"), h0, h1, "hoist divide")
        self.h_stop = find_one(self.rom, bytes.fromhex("D2FC"), self.h_start, h1, ".curve_next adda")
        # fill: from the instruction after `move.w d5,d4` (3805) that follows `sub.w d4,d2 ; ble`
        i = find_one(self.rom, bytes.fromhex("9444"), b0, b1, "entry length sub.w d4,d2")
        j = find_one(self.rom, bytes.fromhex("3805"), i, b1, "move.w d5,d4")
        if (i | j) & 1:
            raise Stop(f"{self.name}: fill anchors on odd addresses ({i:#x}, {j:#x})")
        self.f_start = j + 2
        # ... to the carry park after the loop (see _park)
        self.f_stop = self._park(b1)
        # The SHIPPED loop reads the span back out of the record (`move.w d16(a1),d5`, 3A29),
        # and the hoist stores it BEFORE the divide this tool starts at: seed that word so the
        # reference loop sees what the engine gives it. The new loop reads no span.
        k = self.rom.find(bytes.fromhex("3A29"), self.f_start, self.f_stop)
        self.span_disp = s16((self.rom[k + 2] << 8) | self.rom[k + 3]) if k >= 0 else None

    def _park(self, b1):
        # The park is the first `move.w d1,(abs).w` AFTER the loop's backward branch. Walk from
        # f_start with the interpreter's own length rules is overkill: the park pair is
        # `31C1 xxxx 31C6 yyyy` and the seed park BEFORE f_start is excluded by the range.
        p = find_one(self.rom, bytes.fromhex("31C1"), self.f_start, b1, "carry park")
        if self.rom[p + 4:p + 6] != bytes.fromhex("31C6"):
            raise Stop(f"{self.name}: park at {p:#x} is not `move.w d1 / move.w d6`")
        return p

    def derive(self, spread, span):
        """Run the hoist tail; return (step word, frac/rem word) as stored into the record."""
        c = CPU(self.rom)
        c.d[2] = (0xDEAD0000 | (spread & M16))       # high word garbage: ext.l must ignore it
        c.d[4] = span
        c.a[1] = 0x10000
        if self.span_disp is not None:
            c.mem[0x10000 + self.span_disp] = span
        c.run(self.h_start, self.h_stop)
        return c.mem, c

    def fill(self, rec_mem, acc, err, lines, a4=0x20000):
        c = CPU(self.rom)
        c.mem = dict(rec_mem)
        c.a[1] = 0x10000
        c.a[4] = a4
        c.d[0] = 0xABCD0000 | (acc & M16)          # packed FG<<16 | BG, as the band hoist leaves it
        c.d[1] = acc & M16
        c.d[6] = err & M16
        c.d[2] = lines
        c.d[4] = 0
        c.d[5] = lines
        c.run(self.f_start, self.f_stop, max_steps=20 * lines + 64)
        out = [c.mem[a4 + 4 * k + 2] for k in range(lines)]
        fg = {c.mem[a4 + 4 * k] for k in range(lines)}
        if fg != {0xABCD}:
            raise Stop(f"{self.name}: FG word not constant: {fg}")
        return out, c.d[1] & M16, c.d[6] & M16


def expect(base, spread, span, k0, n):
    return [(base + (k * spread) // span) & M16 for k in range(k0, k0 + n)]


def check(B, sample, seed):
    bad = {"exhaustive": 0, "split": 0}
    cases = {"exhaustive": 0, "split": 0}
    first = []
    for span in range(1, 225):
        for rem in range(span):
            for spread in (rem, rem - span):
                rec, _ = B.derive(spread, span)
                out, _, _ = B.fill(rec, 0, 0, 224)
                exp = expect(0, spread, span, 0, 224)
                cases["exhaustive"] += 1
                if out != exp:
                    bad["exhaustive"] += 1
                    if len(first) < 5:
                        k = next(i for i in range(224) if out[i] != exp[i])
                        first.append(f"span {span} spread {spread}: first bad line {k} got {out[k]} want {exp[k]}")
    rng = random.Random(seed)
    for _ in range(sample):
        span = rng.randint(1, 224)
        spread = rng.randint(-32768, 32767)
        base = rng.randint(0, 65535)
        cut = rng.randint(0, span)
        rec, _ = B.derive(spread, span)
        out1, acc, err = B.fill(rec, base, 0, cut) if cut else ([], base, 0)
        out2, _, _ = B.fill(rec, acc, err, span - cut) if span - cut else ([], 0, 0)
        exp = expect(base, spread, span, 0, span)
        cases["split"] += 1
        if out1 + out2 != exp:
            bad["split"] += 1
            if len(first) < 10:
                first.append(f"split span {span} spread {spread} base {base} cut {cut}")
    return bad, cases, first


def main():
    args = sys.argv[1:]
    sample = 20000
    seed = 1
    if "--sample" in args:
        i = args.index("--sample"); sample = int(args[i + 1]); del args[i:i + 2]
    if "--seed" in args:
        i = args.index("--seed"); seed = int(args[i + 1]); del args[i:i + 2]
    roms = [(args[0], args[1])]
    if "--ref" in args:
        i = args.index("--ref"); roms.insert(0, (args[i + 1], args[i + 2]))
    rc = 0
    for rom, lst in roms:
        try:
            B = Blocks(rom, lst)
        except Stop as e:
            print(f"COULD NOT RUN: {e}")
            return 2
        print(f"{B.name} crc={B.crc:08x} size={len(B.rom)} hoist ${B.h_start:X}..${B.h_stop:X} "
              f"fill ${B.f_start:X}..${B.f_stop:X}")
        try:
            bad, cases, first = check(B, sample, seed)
        except Stop as e:
            print(f"  STOPPED: {e}")
            rc = max(rc, 1)
            continue
        for fam in ("exhaustive", "split"):
            print(f"  {fam}: cases={cases[fam]} mismatches={bad[fam]}")
        for f in first:
            print(f"    {f}")
        if bad["exhaustive"] or bad["split"]:
            rc = max(rc, 1)
    print(f"rc={rc}")
    print("finished=1")
    return rc


if __name__ == "__main__":
    sys.exit(main())
