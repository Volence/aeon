#!/usr/bin/env python3
"""clip_bg_scroll.py — a Sonic 2 zone's own background SCROLL, derived from s2.asm, as aeon scene data.

S2-COMPRESSED-ACT, parcel B-2 of `docs/research/2026-09-25-s2clip-longer-cpz-and-original-bgs.md`
§4 (B-1 put each zone's own background on Plane B, static; this makes it scroll the way Sonic 2
scrolls it). The output is DATA for the engine's existing parallax mechanism — a scene
(`engine/level/scene_dsl.emp` `scene()` / `layer()`), lowered by the registry's `lowerN` into a
`parallax_config` + band records and bound to the zone's region preset through
`preset(parallax: ...)`. No engine code is involved: every band below is a layer the scene model
already expresses.

WHERE THE NUMBERS COME FROM — SOURCE, NOT A TABLE IN A PLAN.
  * EMERALD HILL is DERIVED BY RUNNING SONIC 2'S OWN CODE. `SwScrl_EHZ` (s2.asm) is executed by
    the small 68000-subset interpreter below at several camera X values; the Horiz_Scroll_Buf it
    writes is the ground truth. Every band boundary is where the store LOOP that wrote a line
    changes, every factor is the exact ratio -word/camX at two power-of-two camera positions,
    and the ripple lines are the ones whose word moves when the ripple table does. Nothing in
    this file says "22" or "58".
  * CHEMICAL PLANT cannot be run the same way (`SwScrl_CPZ` branches through a Duff's device and
    a shared scroll-flag routine), so its structure is READ with anchored patterns, each one
    refused by name when absent: InitCam_CPZ's shifts (BG_Y = camY>>2, BG2_X = camX>>1,
    BG_X = camX>>3), cross-checked against SwScrl_CPZ's per-frame `asl.l` rates; the 16-line
    block size (`lsr.w #4`); and the special block number (`cmpi.b #18,d4`) below which rows take
    BG_X, at which they take BG_X + ripple, and above which they take BG2_X.

WHAT THE ENGINE EXPRESSES EXACTLY, AND WHAT IT APPROXIMATES (measured by `compare()`):
  * EHZ flat bands (still sky, camX/64, camX/16, 3camX/32): exact ratios. The engine shifts +camX
    and negates, S2 negates and shifts, so the two differ by the floor-vs-ceil of one shift:
    at most 1 px, on frames whose camX is not a multiple of the divisor.
  * EHZ's lower ramp (camX/8 growing by camX/128 a line): ONE curve layer, camX/8 -> 3camX/4 at
    the screen bottom, EXACT ON THE FIRST LINE OF EVERY GROUP. S2 writes it in single lines, then
    pairs, then triples (the same value held for 2 or 3 lines); the engine's curve is per line,
    so inside a pair or triple it runs 1-2 steps (camX/128 px each) ahead. Expressing the holds
    would take one flat band per group — 39 bands against MAX_PARALLAX_BANDS 16.
  * S2 writes only 222 of 224 lines (a known bug; K&S2 writes the last two with the ramp's last
    value). The curve runs to line 224, which is the fixed behaviour.
  * THE RIPPLE IS STATIC (brief: "leave the water ripple static for now"). Its SHAPE is exact —
    the 32-entry cycle of SwScrl_RippleData, sampled at S2's own frame-0 phase (InitCam clears
    TempArray_LayerDef) — but S2 advances it one entry every 8 frames and aeon's deform phase
    advances in whole entries per frame. Speed 0 until a sub-frame phase exists (engine gap,
    aurora survey).
  * CPZ (approximated, see `derive_cpz`): exact band structure and ratios for background rows
    0..511; rows past 511 do not exist in the 64-row plane, so the vertical clamp stops the
    background at BG Y 288 (camera Y ≈ 1408 + the paste offset) where S2 continues to 456.
"""

import os
import re
import sys
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SCREEN_LINES = 224
PLANE_LINES = 512          # engine PLANE_B_SPAN (scene_dsl pins it); a band top must be below it
LOCKED = 15                # the engine's shift sentinel: s1 15 = factor 0, v_factor 15 = locked
MAX_BANDS = 16             # MAX_PARALLAX_BANDS
DEFORM_TABLE_LEN = 256


class ClipScrollError(Exception):
    """A named refusal."""


# ---------------------------------------------------------------------------
# source access
# ---------------------------------------------------------------------------

def s2_asm_path(donor):
    import s2_donor as sd
    return os.path.join(sd.donor_root(donor), "s2.asm")


def _lines(text):
    return text.split("\n")


def _span(lines, label, what):
    """(first line index after `label:`, index of the next top-level label). Refused if absent."""
    start = next((i for i, ln in enumerate(lines) if ln.rstrip() == label + ":"), None)
    if start is None:
        raise ClipScrollError(f"s2.asm has no `{label}:` ({what})")
    end = next((i for i in range(start + 1, len(lines))
                if re.match(r"^[A-Za-z_][\w]*:", lines[i])), len(lines))
    return start + 1, end


def _fixbugs(lines):
    for ln in lines:
        m = re.match(r"^fixBugs\s*=\s*(\d+)", ln)
        if m:
            return int(m.group(1))
    raise ClipScrollError("s2.asm declares no `fixBugs = N`; the conditional paths cannot be chosen")


def _assemble(lines, start, end, fixbugs):
    """The routine's instructions in source order, as (1-based s2.asm line, label, op, args),
    with `if fixBugs` / `else` / `endif` resolved against the source's own switch. Anonymous
    `-`/`+` labels are kept; comments and blank lines dropped."""
    out, stack = [], []
    for i in range(start, end):
        raw = lines[i].split(";", 1)[0].rstrip()
        s = raw.strip()
        if not s:
            continue
        m = re.match(r"^if\s+(\w+)$", s)
        if m:
            if m.group(1) != "fixBugs":
                raise ClipScrollError(f"s2.asm:{i + 1}: unhandled conditional `{s}`")
            stack.append(bool(fixbugs))
            continue
        if s == "else":
            stack[-1] = not stack[-1]
            continue
        if s == "endif":
            stack.pop()
            continue
        if stack and not all(stack):
            continue
        label = None
        if raw[:1] in "-+" and (len(raw) == 1 or raw[1] in " \t"):
            label, s = raw[0], raw[1:].strip()
        elif raw[:1] not in " \t":
            label, s = raw.split(":", 1)[0], raw.split(":", 1)[1].strip() if ":" in raw else ""
        if not s:
            out.append((i + 1, label, None, None))
            continue
        parts = s.split(None, 1)
        out.append((i + 1, label, parts[0].lower(), parts[1].strip() if len(parts) > 1 else ""))
    return out


def _dc_bytes(lines, label):
    start, end = _span(lines, label, "data table")
    vals = []
    for i in range(start, end):
        s = lines[i].split(";", 1)[0].strip()
        if s.startswith("dc.b"):
            vals.extend(_num(v) for v in s[4:].split(","))
        elif s and s != "even":
            break
    return vals


def _num(tok):
    tok = tok.strip()
    expr = re.sub(r"\$([0-9A-Fa-f]+)", lambda m: str(int(m.group(1), 16)), tok)
    if not re.fullmatch(r"[0-9+\-*/() ]+", expr):
        raise ClipScrollError(f"cannot evaluate `{tok}` as a constant")
    return int(eval(expr.replace("/", "//")))          # noqa: S307 — digits and + - * / only


# ---------------------------------------------------------------------------
# the 68000-subset interpreter (exactly what SwScrl_EHZ uses; anything else is refused)
# ---------------------------------------------------------------------------

_SIZE = {"b": 8, "w": 16, "l": 32}


def _sx(v, bits):
    v &= (1 << bits) - 1
    return v - (1 << bits) if v >> (bits - 1) else v


class _Machine:
    def __init__(self, prog, mem, tables):
        self.prog = prog
        self.mem = dict(mem)            # "Name" -> value (a word/long cell; +N for bytes)
        self.tables = tables            # "Name" -> list of byte values (ROM data)
        self.d = [0] * 8
        self.a = [None] * 8             # (region, byte offset)
        self.z = False
        self.buf = {}                   # Horiz_Scroll_Buf byte offset of a WORD -> value
        self.writer = {}                # same offset -> s2.asm line of the store
        self.loop_of = {}               # same offset -> s2.asm line of the enclosing dbf

    # -- operands --
    def _mem_ref(self, arg):
        m = re.fullmatch(r"\((\w+)([+-]\d+)?\)\.[wl]", arg)
        return (m.group(1), int(m.group(2) or 0)) if m else None

    def read(self, arg, bits):
        if arg.startswith("#"):
            return _num(arg[1:]) & ((1 << bits) - 1)
        if re.fullmatch(r"d[0-7]", arg):
            return self.d[int(arg[1])] & ((1 << bits) - 1)
        m = re.fullmatch(r"\(a([0-7])\)\+", arg)
        if m:
            reg, off = self.a[int(m.group(1))]
            n = bits // 8
            self.a[int(m.group(1))] = (reg, off + n)
            if reg in self.tables and bits == 8:
                return self.tables[reg][off] & 0xFF
            raise ClipScrollError(f"read {bits} bits through {arg} into {reg}")
        ref = self._mem_ref(arg)
        if ref:
            name, off = ref
            if name == "Vint_runcount" and bits == 8:
                return (self.mem.get("Vint_runcount", 0) >> (8 * (3 - off))) & 0xFF
            if off:
                raise ClipScrollError(f"offset read {arg}")
            if name not in self.mem:
                raise ClipScrollError(f"SwScrl read of RAM `{name}`, which this model does not seed")
            return self.mem[name] & ((1 << bits) - 1)
        raise ClipScrollError(f"unsupported source operand `{arg}`")

    def write(self, arg, bits, val, line, loop):
        val &= (1 << bits) - 1
        m = re.fullmatch(r"d([0-7])", arg)
        if m:
            r = int(m.group(1))
            mask = (1 << bits) - 1
            self.d[r] = ((self.d[r] & ~mask) | val) & 0xFFFFFFFF
            return
        m = re.fullmatch(r"\(a([0-7])\)\+", arg)
        if m:
            reg, off = self.a[int(m.group(1))]
            if reg != "Horiz_Scroll_Buf":
                raise ClipScrollError(f"store through {arg} into {reg}")
            words = [(val >> 16) & 0xFFFF, val & 0xFFFF] if bits == 32 else [val]
            for k, w in enumerate(words):
                self.buf[off + 2 * k] = w
                self.writer[off + 2 * k] = line
                self.loop_of[off + 2 * k] = loop
            self.a[int(m.group(1))] = (reg, off + bits // 8)
            return
        ref = self._mem_ref(arg)
        if ref and not ref[1]:
            self.mem[ref[0]] = val
            return
        raise ClipScrollError(f"unsupported destination operand `{arg}`")

    # -- execution --
    def run(self, max_steps=200000):
        prog = self.prog
        pc, steps = 0, 0
        while pc < len(prog):
            steps += 1
            if steps > max_steps:
                raise ClipScrollError("SwScrl did not return")
            line, _label, op, args = prog[pc]
            if op is None:
                pc += 1
                continue
            loop = self._loop_line(pc)
            base, _, sz = op.partition(".")
            bits = _SIZE.get(sz, 16)
            ops = _split_args(args)
            nxt = pc + 1
            if base == "rts":
                return
            elif base == "tst":
                self.z = self.read(ops[0], bits) == 0
            elif base in ("bne", "beq", "bra"):
                if base == "bra" or (base == "bne") != self.z:
                    nxt = self._target(pc, ops[0])
            elif base == "dbf":
                r = int(ops[0][1])
                c = (self.d[r] - 1) & 0xFFFF
                self.d[r] = (self.d[r] & 0xFFFF0000) | c
                if c != 0xFFFF:
                    nxt = self._target(pc, ops[1])
            elif base == "move":
                v = self.read(ops[0], bits)
                self.write(ops[1], bits, v, line, loop)
                self.z = v == 0
            elif base == "moveq":
                self.d[int(ops[1][1])] = _sx(_num(ops[0][1:]), 8) & 0xFFFFFFFF
            elif base == "lea":
                self.a[int(ops[1][1])] = self._ea(ops[0])
            elif base == "neg":
                self.write(ops[0], bits, -self.read(ops[0], bits), line, loop)
            elif base == "swap":
                r = int(ops[0][1])
                self.d[r] = ((self.d[r] << 16) | (self.d[r] >> 16)) & 0xFFFFFFFF
            elif base == "ext":
                r = int(ops[0][1])
                if bits == 16:
                    self.write(ops[0], 16, _sx(self.d[r], 8), line, loop)
                else:
                    self.d[r] = _sx(self.d[r], 16) & 0xFFFFFFFF
            elif base in ("asr", "asl", "lsr"):
                n = _num(ops[0][1:])
                v = self.read(ops[1], bits)
                if base == "asr":
                    v = _sx(v, bits) >> n
                elif base == "lsr":
                    v >>= n
                else:
                    v <<= n
                self.write(ops[1], bits, v, line, loop)
            elif base in ("add", "sub", "subq", "addq"):
                a_ = self.read(ops[0], bits)
                b_ = self.read(ops[1], bits)
                v = b_ + a_ if base in ("add", "addq") else b_ - a_
                self.write(ops[1], bits, v, line, loop)
                self.z = (v & ((1 << bits) - 1)) == 0
            elif base == "andi":
                v = self.read(ops[1], bits) & self.read(ops[0], bits)
                self.write(ops[1], bits, v, line, loop)
                self.z = v == 0
            elif base == "divs":
                src = _sx(self.read(ops[0], 16), 16)
                r = int(ops[1][1])
                num = _sx(self.d[r], 32)
                if src == 0:
                    raise ClipScrollError(f"s2.asm:{line}: divide by zero")
                q = int(num / src)
                rem = num - q * src
                if not -0x8000 <= q <= 0x7FFF:
                    raise ClipScrollError(f"s2.asm:{line}: divs overflow at this camera X")
                self.d[r] = ((rem & 0xFFFF) << 16) | (q & 0xFFFF)
            else:
                raise ClipScrollError(f"s2.asm:{line}: instruction `{op}` is outside the "
                                      f"interpreter's subset")
            pc = nxt

    def _ea(self, arg):
        m = re.fullmatch(r"\((\w+)\)\.[wl]", arg)
        if m:
            return (m.group(1), 0)
        m = re.fullmatch(r"\(a([0-7]),d([0-7])\.w\)", arg)
        if m:
            reg, off = self.a[int(m.group(1))]
            return (reg, off + _sx(self.d[int(m.group(2))], 16))
        raise ClipScrollError(f"unsupported lea operand `{arg}`")

    def _target(self, pc, tok):
        prog = self.prog
        if tok and set(tok) <= {"-"}:
            n, i = len(tok), pc
            while n:
                i -= 1
                if prog[i][1] == "-":
                    n -= 1
            return i
        if tok and set(tok) <= {"+"}:
            n, i = len(tok), pc
            while n:
                i += 1
                if prog[i][1] == "+":
                    n -= 1
            return i
        idx = next((i for i, p in enumerate(prog) if p[1] == tok), None)
        if idx is None:
            raise ClipScrollError(f"branch to `{tok}`, outside the routine")
        return idx

    def _loop_line(self, pc):
        """The s2.asm line of the dbf that closes the loop containing pc (None outside one)."""
        prog = self.prog
        for j in range(pc, len(prog)):
            if prog[j][2] == "dbf":
                tgt = self._target(j, _split_args(prog[j][3])[1])
                if tgt <= pc:
                    return prog[j][0]
                return None
            if prog[j][2] == "rts":
                return None
        return None


def _split_args(args):
    out, depth, cur = [], 0, ""
    for ch in args or "":
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


# ---------------------------------------------------------------------------
# factor encoding (engine/level/parallax_dsl.emp `packed(s1, s2, op)`)
# ---------------------------------------------------------------------------

def factor_value(s1, s2, op):
    if s1 == LOCKED:
        return Fraction(0)
    v = Fraction(1, 1 << s1)
    if s2 != LOCKED:
        v = v - Fraction(1, 1 << s2) if op else v + Fraction(1, 1 << s2)
    return v


def encode_factor(r):
    """The (s1, s2, op) the engine decodes back to exactly r. Refused when r is not 2^-a or
    2^-a +- 2^-b with shifts 0..14. PREFERENCE: one term, then ADD, then SUB — because Sonic 2
    builds its two-term factors by adding (EHZ's 3camX/32 is `camX>>4 + camX>>4>>1`), and an
    ADD pair floors each term the way that sum does."""
    if r == 0:
        return (LOCKED, LOCKED, 0)
    for s1 in range(15):
        if factor_value(s1, LOCKED, 0) == r:
            return (s1, LOCKED, 0)
    for op in (0, 1):
        for s1 in range(15):
            for s2 in range(s1 + 1, 15):
                if factor_value(s1, s2, op) == r:
                    return (s1, s2, op)
    raise ClipScrollError(f"scroll ratio {r} is not expressible as one engine factor "
                          f"(2^-a, or 2^-a +- 2^-b, shifts 0..14)")


def factor_text(f):
    return f"packed(s1: {f[0]}, s2: {f[1]}, op: {f[2]})"


def _floor_shift(x, s):
    return x >> s


def engine_factor_scroll(f, camx):
    """Decode_Factor_B's value for camera X (positive; the HScroll word is its negation)."""
    s1, s2, op = f
    if s1 == LOCKED:
        return 0
    v = _floor_shift(camx, s1)
    if s2 != LOCKED:
        v = v - _floor_shift(camx, s2) if op else v + _floor_shift(camx, s2)
    return v


# ---------------------------------------------------------------------------
# EMERALD HILL — run SwScrl_EHZ
# ---------------------------------------------------------------------------

def _ehz_program(text):
    lines = _lines(text)
    fb = _fixbugs(lines)
    s, e = _span(lines, "SwScrl_EHZ", "Emerald Hill's scroll routine")
    prog = _assemble(lines, s, e, fb)
    ripple = _dc_bytes(lines, "SwScrl_RippleData")
    return prog, ripple, lines, (s + 1)


def run_swscrl_ehz(text, camx, ripple_phase=0, ripple_override=None, frame=1):
    """Sonic 2's own Horiz_Scroll_Buf for one call: [(fg, bg) or None per screen line], and the
    s2.asm line of the dbf loop that wrote each line."""
    prog, ripple, _l, _s = _ehz_program(text)
    tab = [(_sx(v, 8) & 0xFF) for v in (ripple_override or ripple)]
    mem = {"Two_player_mode": 0, "Camera_X_pos": camx & 0xFFFF, "Camera_BG_Y_pos": 0,
           "Vscroll_Factor_BG": 0, "Vint_runcount": frame, "TempArray_LayerDef": ripple_phase}
    m = _Machine(prog, mem, {"SwScrl_RippleData": tab})
    m.a[1] = None
    m.run()
    rows, loops = [], []
    for line in range(SCREEN_LINES):
        off = line * 4
        if off in m.buf and off + 2 in m.buf:
            rows.append((m.buf[off], m.buf[off + 2]))
            loops.append(m.loop_of[off + 2])
        else:
            rows.append(None)
            loops.append(None)
    if any(k >= SCREEN_LINES * 4 for k in m.buf):
        raise ClipScrollError("SwScrl_EHZ wrote past the 224-line scroll buffer")
    return rows, loops


def _ripple_cycle(ripple):
    """The ripple table's cycle length and one cycle, derived (not assumed to be 32)."""
    n = len(ripple)
    for p in range(1, n):
        if all(ripple[i] == ripple[i + p] for i in range(n - p)):
            return p, ripple[:p]
    raise ClipScrollError("SwScrl_RippleData does not repeat")


def ripple_table(text):
    """The engine's 256-byte deform table: SwScrl_RippleData's cycle, repeated. Refused unless
    the cycle divides 256 (the engine's index wraps at 256)."""
    _p, ripple, _l, _s = _ehz_program(text)
    p, cyc = _ripple_cycle(ripple)
    if DEFORM_TABLE_LEN % p:
        raise ClipScrollError(f"the ripple cycle is {p} entries, which does not divide the "
                              f"engine's {DEFORM_TABLE_LEN}-entry deform table")
    return [_sx(cyc[i % p], 8) for i in range(DEFORM_TABLE_LEN)], p


def _bg_signed(w):
    return _sx(w, 16)


def derive_ehz(text):
    """Emerald Hill's scene, derived by running SwScrl_EHZ. Returns a spec dict."""
    lines = _lines(text)
    # vertical: InitCam_EHZ clears Camera_BG_Y_pos and SwScrl_EHZ copies it unchanged.
    s, e = _span(lines, "InitCam_EHZ", "Emerald Hill's camera init")
    init = "\n".join(lines[s:e])
    if not re.search(r"clr\.l\s+\(Camera_BG_Y_pos\)\.w", init):
        raise ClipScrollError("InitCam_EHZ does not clear Camera_BG_Y_pos; the lock is not proven")
    prog, ripple, _l, _ = _ehz_program(text)
    bgy_writes = [p[0] for p in prog if p[3] and re.search(r",\s*\(Camera_BG_Y_pos\)", p[3])]
    if bgy_writes:
        raise ClipScrollError(f"SwScrl_EHZ writes Camera_BG_Y_pos (s2.asm:{bgy_writes}); the "
                              f"background is not vertically locked")
    vcopy = [p[0] for p in prog if p[2] == "move.w" and
             p[3].replace(" ", "") == "(Camera_BG_Y_pos).w,(Vscroll_Factor_BG).w"]
    if len(vcopy) != 1:
        raise ClipScrollError("SwScrl_EHZ's vertical scroll is not the one Camera_BG_Y_pos copy")

    big, half = 8192, 4096                      # two power-of-two camera X values
    rows_b, loops = run_swscrl_ehz(text, big)
    rows_h, _ = run_swscrl_ehz(text, half)
    # ripple lines: the ones that move when every ripple byte is 64 instead of the real data
    rows_s, _ = run_swscrl_ehz(text, big, ripple_override=[64] * len(ripple))
    rows_z, _ = run_swscrl_ehz(text, big, ripple_override=[0] * len(ripple))
    written = [i for i in range(SCREEN_LINES) if rows_b[i] is not None]
    if written != list(range(len(written))):
        raise ClipScrollError("SwScrl_EHZ leaves a gap inside the lines it writes")
    n_written = len(written)
    for i in written:
        if _bg_signed(rows_b[i][0]) != -big or _bg_signed(rows_h[i][0]) != -half:
            raise ClipScrollError(f"line {i}: the foreground word is not -camX")

    def ratio(rows, c, i):
        return Fraction(-_bg_signed(rows[i][1]), c)

    ripple_line = [_bg_signed(rows_s[i][1]) - _bg_signed(rows_z[i][1]) == 64 for i in written]
    base = [ratio(rows_z, big, i) for i in written]
    base_h = [Fraction(-_bg_signed(run_swscrl_ehz(text, half, ripple_override=[0] * len(ripple))[0][i][1]), half)
              for i in written]
    # segments: maximal runs written by the same store loop
    segs = []
    for i in written:
        if segs and segs[-1]["loop"] == loops[i]:
            segs[-1]["lines"].append(i)
        else:
            segs.append({"loop": loops[i], "lines": [i]})
    bands = []
    for sg in segs:
        ls = sg["lines"]
        vals = {base[i] for i in ls}
        rip = {ripple_line[i] for i in ls}
        if len(rip) != 1:
            raise ClipScrollError(f"the loop at s2.asm:{sg['loop']} mixes ripple and plain lines")
        if len(vals) == 1:
            r = base[ls[0]]
            if any(base_h[i] != r for i in ls):
                raise ClipScrollError(f"lines {ls[0]}..{ls[-1]} (s2.asm:{sg['loop']}) do not scroll "
                                      f"at one ratio of camX: {r} at camX {big} but not at {half}")
            kind = "ripple" if rip.pop() else "flat"
            if (bands and bands[-1]["kind"] == kind and bands[-1]["ratio"] == r):
                bands[-1]["end"] = ls[-1] + 1
                bands[-1]["loops"].append(sg["loop"])
            else:
                bands.append({"kind": kind, "top": ls[0], "end": ls[-1] + 1, "ratio": r,
                              "loops": [sg["loop"]]})
        else:
            if bands and bands[-1]["kind"] == "ramp":
                bands[-1]["end"] = ls[-1] + 1
                bands[-1]["loops"].append(sg["loop"])
                bands[-1]["lines"].extend(ls)
            else:
                bands.append({"kind": "ramp", "top": ls[0], "end": ls[-1] + 1,
                              "ratio": base[ls[0]], "loops": [sg["loop"]], "lines": list(ls)})
    # the ramp: exact on every group's first line, slope from the last group start
    for b in bands:
        if b["kind"] != "ramp":
            continue
        ls = b["lines"]
        starts = [i for i in ls if i == ls[0] or base[i] != base[i - 1]]
        last = starts[-1]
        slope = (base[last] - base[ls[0]]) / (last - ls[0])
        for i in ls:
            g = max(s_ for s_ in starts if s_ <= i)
            if base[i] != base[ls[0]] + slope * (g - ls[0]):
                raise ClipScrollError(f"the ramp at line {i} is not linear in its group starts")
            if base_h[i] != base_h[ls[0]] + (base_h[last] - base_h[ls[0]]) / (last - ls[0]) * (g - ls[0]):
                raise ClipScrollError(f"the ramp at line {i} is not one ratio of camX")
        holds = []
        for k, st in enumerate(starts):
            nxt = starts[k + 1] if k + 1 < len(starts) else ls[-1] + 1
            holds.append(nxt - st)
        b["slope"] = slope
        b["holds"] = holds
        del b["lines"]
    # the engine's band ends where the next begins; the last runs to the screen bottom
    for k, b in enumerate(bands):
        b["engine_end"] = bands[k + 1]["top"] if k + 1 < len(bands) else SCREEN_LINES
        b["factor"] = encode_factor(b["ratio"])
        if b["kind"] == "ramp":
            b["to_ratio"] = b["ratio"] + b["slope"] * (b["engine_end"] - b["top"])
            b["to_factor"] = encode_factor(b["to_ratio"])
    if bands[0]["top"] != 0:
        raise ClipScrollError("SwScrl_EHZ's first written line is not screen line 0")
    if len(bands) > MAX_BANDS:
        raise ClipScrollError(f"Emerald Hill needs {len(bands)} bands; the engine holds {MAX_BANDS}")
    table, cycle = ripple_table(text)
    for b in bands:
        # the band's first line reads cycle entry 0, S2's frame-0 phase (InitCam_EHZ clears
        # TempArray_LayerDef): index = phase + Vscroll_BG(0) + screen line
        b["phase"] = (-b["top"]) & 0xFF if b["kind"] == "ripple" else 0
        b["plane_top"] = b["top"]
    return {"zone": "EHZ", "routine": "SwScrl_EHZ", "v_factor": LOCKED, "v_center": 0,
            "v_offset": 0, "bands": bands, "written_lines": n_written,
            "ripple_cycle": cycle, "deform_table": table,
            "provenance": {"SwScrl_EHZ": _span(lines, "SwScrl_EHZ", "")[0],
                           "InitCam_EHZ": s, "SwScrl_RippleData": _span(lines, "SwScrl_RippleData", "")[0]}}


# ---------------------------------------------------------------------------
# CHEMICAL PLANT — read SwScrl_CPZ / InitCam_CPZ
# ---------------------------------------------------------------------------

def _find(pattern, text, what, lines_off, flags=0):
    m = re.search(pattern, text, flags)
    if not m:
        raise ClipScrollError(f"CPZ: {what} not found in s2.asm (pattern {pattern!r})")
    return m, lines_off + text[:m.start()].count("\n") + 1


def derive_cpz(text, paste_dy):
    """Chemical Plant's scene, APPROXIMATED to the 512-line plane. paste_dy is the clip's
    dst.y - src.y (the act world Y of Sonic 2's Y 0)."""
    lines = _lines(text)
    s, e = _span(lines, "InitCam_CPZ", "Chemical Plant's camera init")
    init = "\n".join(lines[s:e])
    m_v, ln_v = _find(r"lsr\.w\s+#(\d+),d0\s*\n\s*move\.w\s+d0,\(Camera_BG_Y_pos\)\.w", init,
                      "InitCam_CPZ's BG Y shift", s)
    m_x, ln_x = _find(r"lsr\.w\s+#(\d+),d1\s*\n\s*move\.w\s+d1,\(Camera_BG2_X_pos\)\.w\s*\n"
                      r"\s*lsr\.w\s+#(\d+),d1\s*\n\s*move\.w\s+d1,\(Camera_BG_X_pos\)\.w",
                      init, "InitCam_CPZ's BG2 X / BG X shifts", s)
    v_shift = int(m_v.group(1))
    bg2_shift = int(m_x.group(1))
    bg_shift = bg2_shift + int(m_x.group(2))
    s2_, e2 = _span(lines, "SwScrl_CPZ", "Chemical Plant's scroll routine")
    body = "\n".join(lines[s2_:e2])
    # per-frame rates: Camera_*_pos_diff is 8.8 px, a camera position 16.16, so asl.l #n adds
    # diff * 2^(n+8-16) px — a shift of 8-n.
    m_r, ln_r = _find(r"move\.w\s+\(Camera_X_pos_diff\)\.w,d4\s*\n\s*ext\.l\s+d4\s*\n\s*asl\.l\s+#(\d+),d4"
                      r"\s*\n\s*move\.w\s+\(Camera_Y_pos_diff\)\.w,d5\s*\n\s*ext\.l\s+d5\s*\n\s*asl\.l\s+#(\d+),d5"
                      r"\s*\n\s*bsr\.w\s+SetHorizVertiScrollFlagsBG", body, "SwScrl_CPZ's BG rates", s2_)
    m_r2, ln_r2 = _find(r"move\.w\s+\(Camera_X_pos_diff\)\.w,d4\s*\n\s*ext\.l\s+d4\s*\n\s*asl\.l\s+#(\d+),d4"
                        r"\s*\n\s*moveq\s+#scroll_flag_advanced_bg2_left,d6\s*\n\s*bsr\.w\s+SetHorizScrollFlagsBG2",
                        body, "SwScrl_CPZ's BG2 rate", s2_)
    rates = (8 - int(m_r.group(1)), 8 - int(m_r.group(2)), 8 - int(m_r2.group(1)))
    if rates != (bg_shift, v_shift, bg2_shift):
        raise ClipScrollError(f"CPZ: InitCam_CPZ's shifts (BG X {bg_shift}, BG Y {v_shift}, BG2 X "
                              f"{bg2_shift}) disagree with SwScrl_CPZ's per-frame rates {rates}")
    m_b, ln_b = _find(r"andi\.w\s+#\$([0-9A-Fa-f]+),d0\s*\n\s*lsr\.w\s+#(\d+),d0", body,
                      "SwScrl_CPZ's line-block index", s2_)
    block = 1 << int(m_b.group(2))
    m_k, ln_k = _find(r"\.doFullLineBlock:.*?move\.w\s+\(Camera_BG_X_pos\)\.w,d0\s*\n\s*cmpi\.b\s+#(\d+),d4"
                      r"\s*\n\s*beq\.s\s+\.doFullSpecialLineBlock\s*\n\s*blo\.s\s+\+\s*\n\s*"
                      r"move\.w\s+\(Camera_BG2_X_pos\)\.w,d0", body,
                      "SwScrl_CPZ's special-block test (BG_X below, BG2_X above)", s2_, re.S)
    special = int(m_k.group(1))
    _find(r"\.doFullSpecialLineBlock:.*?move\.w\s+\(Camera_BG_X_pos\)\.w,d3.*?SwScrl_RippleData",
          body, "the special block's BG_X + ripple", s2_, re.S)
    table, cycle = ripple_table(text)
    tops = [0, special * block, (special + 1) * block]
    if tops[-1] >= PLANE_LINES:
        raise ClipScrollError(f"CPZ's plain-BG2 rows start at {tops[-1]}, past the plane")
    bands = [
        {"kind": "flat", "plane_top": tops[0], "ratio": Fraction(1, 1 << bg_shift),
         "src": [ln_x, ln_k], "phase": 0},
        {"kind": "ripple", "plane_top": tops[1], "ratio": Fraction(1, 1 << bg_shift),
         "src": [ln_k], "phase": (-tops[1]) & 0xFF},
        {"kind": "flat", "plane_top": tops[2], "ratio": Fraction(1, 1 << bg2_shift),
         "src": [ln_x, ln_k], "phase": 0},
    ]
    for k, b in enumerate(bands):
        b["factor"] = encode_factor(b["ratio"])
        b["top"] = b["plane_top"]
        b["engine_end"] = bands[k + 1]["plane_top"] if k + 1 < len(bands) else PLANE_LINES
    return {"zone": "CPZ", "routine": "SwScrl_CPZ", "v_factor": v_shift, "v_center": paste_dy,
            "v_offset": 0, "bands": bands, "block": block, "special_block": special,
            "ripple_cycle": cycle, "deform_table": table,
            "provenance": {"InitCam_CPZ BG Y": ln_v, "InitCam_CPZ BG X": ln_x,
                           "SwScrl_CPZ rates": ln_r, "SwScrl_CPZ BG2 rate": ln_r2,
                           "SwScrl_CPZ block index": ln_b, "SwScrl_CPZ special block": ln_k}}


DERIVERS = {"EHZ": lambda text, dy: derive_ehz(text), "CPZ": derive_cpz}


def derive(donor, zone, paste_dy):
    """The spec for one donor zone, or None when this zone has no transcription (the caller
    keeps the act default and says so)."""
    fn = DERIVERS.get(zone)
    if fn is None:
        return None
    with open(s2_asm_path(donor), "r", errors="replace") as fh:
        text = fh.read()
    return fn(text, paste_dy)


# ---------------------------------------------------------------------------
# emission: scene_dsl text
# ---------------------------------------------------------------------------

def layer_world_y(spec, plane_top):
    """scene_plane_line()'s inverse: the act world Y whose plane image is plane_top."""
    vf = spec["v_factor"]
    if vf == LOCKED:
        return plane_top
    return ((plane_top - spec["v_offset"]) << vf) + spec["v_center"]


def uses_ripple(spec):
    return any(b["kind"] == "ripple" for b in spec["bands"])


def scene_text(spec, scene_name, table_label, transition=0):
    """`pub const <scene_name>: Scene = scene(...)` for one spec. `transition` is scene()'s
    TRANS_SMOOTH (0, the default: the config crossing lerps PARALLAX_TRANS_DEFAULT frames) or
    TRANS_INSTANT (1); it is written only when nonzero, so a default scene's text is unchanged."""
    fa = factor_text((0, LOCKED, 0))                     # plane A: camX, the foreground
    rows = []
    for b in spec["bands"]:
        args = [f"world_y: {layer_world_y(spec, b['plane_top'])}", f"fa: {fa}",
                f"fb: {factor_text(b['factor'])}"]
        if b["kind"] == "ripple":
            args += ["dsb: 0", f"phase: {b['phase']}"]
        if b["kind"] == "ramp":
            args.append(f"curve: SceneCurve.To({factor_text(b['to_factor'])})")
        rows.append("layer(" + ", ".join(args) + ")")
    rows += ["no_layer()"] * (MAX_BANDS - len(rows))
    deform = (f",\n    deform_bg: SceneDeform.Shared({table_label}, 0)" if uses_ripple(spec) else "")
    return (f"pub const {scene_name}: Scene = scene(\n"
            f"    layers: [ " + ",\n              ".join(rows) + " ],\n"
            f"    count: {len(spec['bands'])},\n"
            f"    v_factor: {spec['v_factor']},\n"
            f"    v_center: {spec['v_center']},\n"
            f"    v_offset: {spec['v_offset']}{deform}"
            + (f",\n    transition: {transition}" if transition else "") + ")\n")


SCENE_LABEL = "OJZ_Clip_Scene_{key}"
PARALLAX_LABEL = "OJZ_Clip_Parallax_{key}"
TABLE_LABEL = "OJZ_Clip_Deform_Ripple"


def data_uses(counts):
    """The imports the scroll half of the clip data block needs. The two scene_dsl /
    parallax_dsl GLOBS are mandatory (a comptime fn's free names resolve at the CALL site —
    docs/EMP_PITFALLS.md §2), and every band_* name is load-bearing because band_record is
    re-elaborated in the importing module (§8). Same list as effects_gen's editor module."""
    shapes = sorted(set(counts))
    return ("use engine.structs.{parallax_config}\n"
            "use engine.parallax.{band_entry, band_record, band_ext, BAND_EXT_N, band_curve, "
            "BAND_CURVE_N, band_drift, BAND_DRIFT_N, band_remap, BAND_REMAP_N}\n"
            "use engine.level.scene_dsl.*\n"
            "use engine.level.parallax_dsl.*\n"
            "use games.sonic4.scene_registry.{"
            + ", ".join([f"SceneCfg{n}" for n in shapes] + [f"lower{n}" for n in shapes]) + "}\n")


def data_block_text(zones, act_span, transition=0):
    """The scroll half of the CLIP ACT DATA block. `zones` is [(key, spec)] for every zone
    that HAS a spec. Emits the ripple table (once), one scene per zone through the real
    constructors, the three registry-level folds the editor module runs (budget, caps
    subset, act-relative tops) with their results REFERENCED, and one lowered record per
    zone under PARALLAX_LABEL."""
    out = ["// ---- EACH ZONE'S OWN SONIC 2 SCROLL (tools/clip_bg_scroll.py, S2CLIP-ORIGINAL-BGS "
           "B-2) ----\n"
           "// Scenes through the REAL constructors (layer()/scene()), so every scene_dsl guard\n"
           "// fires here; lowered by the registry's lowerN; bound to each zone's region preset\n"
           "// through preset(parallax:). Every number below is derived from s2.asm by\n"
           "// tools/clip_bg_scroll.py (EHZ by RUNNING SwScrl_EHZ), never typed.\n"]
    tables = {tuple(spec["deform_table"]) for _k, spec in zones if uses_ripple(spec)}
    if len(tables) > 1:
        raise ClipScrollError("two zones derive DIFFERENT ripple tables; this block emits one")
    if tables:
        tab = list(tables.pop())
        body = ",\n    ".join(", ".join(str(v) for v in tab[i:i + 32]) for i in range(0, 256, 32))
        out.append(
            "// SwScrl_RippleData's cycle, repeated to the engine's 256-entry deform table. SPEED 0\n"
            "// (static): S2 advances it one entry per 8 frames and the engine's phase moves in\n"
            "// whole entries per frame (booked engine gap).\n"
            f"pub data {TABLE_LABEL}: [i8; 256] = [\n    {body}\n]\n")
    names = []
    for key, spec in zones:
        lab = SCENE_LABEL.format(key=key)
        names.append(lab)
        prov = ", ".join(f"{k} s2.asm line {v}" for k, v in spec["provenance"].items())
        rows = "\n".join(
            f"//   plane line {top:>3}{'' if end is None else f'..{end - 1:<3}'}  {what}"
            for top, end, what, _f, _src in band_rows(spec))
        out.append(f"// zone key {key}: {spec['zone']} ({spec['routine']}; {prov})\n{rows}\n")
        out.append(scene_text(spec, lab, TABLE_LABEL, transition))
    n = len(names)
    tops = sum(len(spec["bands"]) for _k, spec in zones)
    out.append(
        f"pub const OJZ_Clip_Scenes = [{', '.join(names)}]\n"
        "// The editor module's three folds, over the clip scenes — the registry folds the HAND\n"
        "// scenes only, so without these nothing budgets or caps-checks a clip scene. Each result\n"
        "// is REFERENCED by an ensure: an unreferenced const is comptime-inert (EMP_PITFALLS §3).\n"
        "pub const OJZ_Clip_Scenes_BudgetChecked = scene_budget_enforce(OJZ_Clip_Scenes)\n"
        f"ensure(OJZ_Clip_Scenes_BudgetChecked == {n},\n"
        f"       \"clip scenes: the budget fold checked {{OJZ_Clip_Scenes_BudgetChecked}} scenes, "
        f"not the {n} this clip act binds\")\n"
        "pub const OJZ_Clip_Scenes_CapsFolded = fold_caps(OJZ_Clip_Scenes)\n"
        "ensure((OJZ_Clip_Scenes_CapsFolded & ~Game.SCANLINE_CAPS) == 0,\n"
        "       \"clip scenes: the folded capability mask {OJZ_Clip_Scenes_CapsFolded} is not a "
        "subset of Game.SCANLINE_CAPS {Game.SCANLINE_CAPS} — a Sonic 2 scroll transcription "
        "demands a scanline service this game does not declare\")\n"
        f"pub const OJZ_Clip_Scenes_ActChecked = assert_act_relative_tagged(OJZ_Clip_Scenes, {act_span})\n"
        f"ensure(OJZ_Clip_Scenes_ActChecked == {tops},\n"
        f"       \"clip scenes: the act-relative fold classified {{OJZ_Clip_Scenes_ActChecked}} "
        f"layer tops, not the {tops} the clip scenes declare\")\n")
    for (key, spec), lab in zip(zones, names):
        c = len(spec["bands"])
        out.append(f"pub data {PARALLAX_LABEL.format(key=key)} (align: 2): SceneCfg{c} = "
                   f"lower{c}({lab})\n")
    return "".join(out)


def band_rows(spec):
    """Human-readable band table: (plane top, engine end, what, factor text, source)."""
    out = []
    for b in spec["bands"]:
        what = {"flat": f"camX*{b['ratio']}", "ripple": f"camX*{b['ratio']} + ripple (static)",
                "ramp": f"camX*{b['ratio']} -> camX*{b.get('to_ratio')} (curve)"}[b["kind"]]
        out.append((b["plane_top"], b.get("engine_end"), what, b["factor"],
                    b.get("loops") or b.get("src")))
    return out


# ---------------------------------------------------------------------------
# the engine model and the comparison (what the parcel measures)
# ---------------------------------------------------------------------------

def engine_vscroll(spec, camy, ceiling=PLANE_LINES - SCREEN_LINES):
    """Parallax_Step5_Vscroll at steady state: the BG vertical scroll, clamped to
    [0, ceiling] (VSCROLL_BG_MAX when the region authors no rg_bg_span)."""
    if spec["v_factor"] == LOCKED:
        v = spec["v_offset"]
    else:
        v = (_sx(camy - spec["v_center"], 16) >> spec["v_factor"]) + spec["v_offset"]
    return min(max(v, 0), ceiling)


def engine_bg_words(spec, camx, table=None, vscroll=None, phase_bg=0):
    """The BG HScroll word the engine's fill writes on each screen line at steady state
    (Parallax_Fill_PerLine's flat, sampled and curve loops). `vscroll` is the BG plane's
    vertical scroll (a locked scene's v_offset when None); `phase_bg` is
    Parallax_Deform_Phase_BG. Bands are keyed by PLANE line: a screen line L shows plane row
    (vscroll + L) mod 512 and takes the band whose top is the last at or above that row. A
    curve is modelled only on a locked plane (the one place this parcel authors one)."""
    bands = spec["bands"]
    if vscroll is None:
        if spec["v_factor"] != LOCKED:
            raise ClipScrollError("an unlocked scene needs the live vscroll")
        vscroll = spec["v_offset"]
    tab = table or spec.get("deform_table")
    out = [None] * SCREEN_LINES
    if spec["v_factor"] != LOCKED or vscroll:
        if any(b["kind"] == "ramp" for b in bands):
            raise ClipScrollError("a curve on a scrolling plane is not modelled here")
        for line in range(SCREEN_LINES):
            row = (vscroll + line) % PLANE_LINES
            b = [x for x in bands if x["plane_top"] <= row][-1]
            v = -engine_factor_scroll(b["factor"], camx)
            if b["kind"] == "ripple":
                v += tab[(phase_bg + b["phase"] + vscroll + line) & 0xFF]
            out[line] = _sx(v, 16)
        return out
    for k, b in enumerate(bands):
        top = b["plane_top"]
        end = bands[k + 1]["plane_top"] if k + 1 < len(bands) else SCREEN_LINES
        base = _sx(-engine_factor_scroll(b["factor"], camx), 16)
        if b["kind"] == "ramp":
            far = _sx(-engine_factor_scroll(b["to_factor"], camx), 16)
            spread = _sx(far - base, 16)
            span = end - top
            q = int(spread / span)
            r = spread - q * span
            if r < 0:
                r += span
                q -= 1
            acc, err = base, 0
            for line in range(top, end):
                out[line] = _sx(acc, 16)
                acc += q
                err += r
                if err >= span:
                    err -= span
                    acc += 1
        else:
            for line in range(top, end):
                v = base
                if b["kind"] == "ripple":
                    v += tab[(phase_bg + b["phase"] + line) & 0xFF]
                out[line] = _sx(v, 16)
    return out


def group_starts(band):
    """A ramp band's group-start lines (the lines on which Sonic 2 writes a NEW value)."""
    out, line = [], band["top"]
    for h in band["holds"]:
        out.append(line)
        line += h
    return out


def compare(text, spec, camxs):
    """{band index: (worst |engine - Sonic 2| px on the lines where S2 writes a new value,
    worst on the lines where S2 HOLDS the previous group's value)} over camxs, on the lines
    Sonic 2 writes (ripple at S2's frame-0 phase), plus the lines it never writes. For a flat
    or ripple band every line is a 'new value' line and the second figure is 0."""
    starts = {k: set(group_starts(b)) if b["kind"] == "ramp" else None
              for k, b in enumerate(spec["bands"])}
    worst = {k: [0, 0] for k in range(len(spec["bands"]))}
    unwritten = set()
    for c in camxs:
        rows, _ = run_swscrl_ehz(text, c)
        eng = engine_bg_words(spec, c)
        for line in range(SCREEN_LINES):
            if rows[line] is None:
                unwritten.add(line)
                continue
            d = abs(_sx(eng[line] - _bg_signed(rows[line][1]), 16))
            k = max(i for i, b in enumerate(spec["bands"]) if b["plane_top"] <= line)
            slot = 0 if starts[k] is None or line in starts[k] else 1
            worst[k][slot] = max(worst[k][slot], d)
    return {k: tuple(v) for k, v in worst.items()}, sorted(unwritten)


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--donor", default="s2disasm")
    ap.add_argument("--cpz-paste-dy", type=int, default=256)
    a = ap.parse_args(argv)
    with open(s2_asm_path(a.donor), "r", errors="replace") as fh:
        text = fh.read()
    for spec in (derive_ehz(text), derive_cpz(text, a.cpz_paste_dy)):
        print(f"{spec['zone']}: v_factor {spec['v_factor']} v_center {spec['v_center']}")
        for row in band_rows(spec):
            print("   ", row)
    ehz = derive_ehz(text)
    worst, unw = compare(text, ehz, list(range(0, 11000, 37)) + [10975])
    print("EHZ worst |engine - S2| px per band (new-value lines, held lines):", worst,
          "unwritten lines:", unw)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
