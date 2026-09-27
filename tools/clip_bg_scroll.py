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
  * METROPOLIS is READ the same way (`derive_mtz`): InitCam_Index names InitCam_Std for it
    (BG_Y = camY>>2, BG_X = camX>>3), cross-checked against SwScrl_MTZ's per-frame rates, and
    SwScrl_MTZ stores one value on all 224 lines. One flat band, exact.

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
    """The donor's top-level source: s2.asm (final) or main.asm (the prototype, Hidden
    Palace's only donor)."""
    import s2_donor as sd
    return os.path.join(sd.donor_root(donor), "s2.asm" if donor == sd.S2_FINAL else "main.asm")


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
        m = re.match(r"^fixBugs\s*=\s*(\d+)", ln, re.I)       # the prototype spells it FixBugs
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
            if m.group(1).lower() != "fixbugs":
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
        args = parts[1].strip() if len(parts) > 1 else ""
        # the prototype writes some address registers in capitals (`lea (...).w,A1`)
        args = re.sub(r"\b([AD])([0-7])\b", lambda m_: m_.group(1).lower() + m_.group(2), args)
        out.append((i + 1, label, parts[0].lower(), args))
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


class _Symbolic(ClipScrollError):
    """An operand that is a named assembler symbol, not a number."""


def _num(tok):
    tok = tok.strip()
    expr = re.sub(r"\$([0-9A-Fa-f]+)", lambda m: str(int(m.group(1), 16)), tok)
    if not re.fullmatch(r"[0-9+\-*/() ]+", expr):
        raise _Symbolic(f"cannot evaluate `{tok}` as a constant")
    return int(eval(expr.replace("/", "//")))          # noqa: S307 — digits and + - * / only


# ---------------------------------------------------------------------------
# the 68000-subset interpreter (exactly what SwScrl_EHZ uses; anything else is refused)
# ---------------------------------------------------------------------------

_SIZE = {"b": 8, "w": 16, "l": 32}


def _sx(v, bits):
    v &= (1 << bits) - 1
    return v - (1 << bits) if v >> (bits - 1) else v


class _Machine:
    """A 68000 SUBSET, exactly what the transcribed SwScrl routines use; anything else is
    refused by name. Extended 2026-09-27 (woven HPZ/WFZ/OOZ prep) with: local `bsr`/`rts` and
    `addq.l #4,sp` (SwScrl_OOZ's line helpers pop their caller), N and C flags for
    `bmi`/`bpl`/`bcc`/`bcs`/`bhs`/`blo`, `subi`/`addi`/`adda`, pre-decrement stores, stores
    into named RAM arrays other than Horiz_Scroll_Buf (`regions`), `lea label(pc)` onto a ROM
    table, `lea (Name+expr).w`, and two escape hatches that are declared rather than guessed:
    `stubs` (external scroll-FLAG routines, run as no-ops: they set redraw flags and advance a
    BG position the caller seeds directly) and `stop_at` (a `bra` into a shared writer that is
    read by pattern instead of run). A `moveq #<symbol>` POISONS its register: any later read
    of it before a write raises, so an unevaluated flag number can never reach a value."""

    def __init__(self, prog, mem, tables, stubs=(), stop_at=(), regions=()):
        self.prog = prog
        self.mem = dict(mem)            # "Name" -> value (a word/long cell; +N for bytes)
        self.tables = tables            # "Name" -> list of byte values (ROM data)
        self.stubs = set(stubs)
        self.stop_at = set(stop_at)
        self.d = [0] * 8
        self.a = [None] * 8             # (region, byte offset)
        self.z = self.n = self.c = False
        self.poison = {}
        self.stack = []
        self.bufs = {"Horiz_Scroll_Buf": {}}
        for r in regions:
            self.bufs[r] = {}
        self.buf = self.bufs["Horiz_Scroll_Buf"]   # byte offset of a WORD -> value
        self.writer = {}                # (region, offset) -> s2.asm line of the store
        self.loop_of = {}               # Horiz_Scroll_Buf offset -> s2.asm line of the dbf
        self.stopped = None             # the stop_at label reached, if any

    # -- operands --
    def _mem_ref(self, arg):
        m = re.fullmatch(r"\((\w+)([+-]\d+)?\)\.[wl]", arg)
        return (m.group(1), int(m.group(2) or 0)) if m else None

    def _dreg(self, r, bits=32):
        """A data register's value; refused if the bits read still hold part of an
        unevaluated `moveq #symbol` (`poison` maps reg -> {"lo", "hi"} still poisoned)."""
        bad = self.poison.get(r, set())
        if bad and (bits == 32 or "lo" in bad):
            raise ClipScrollError(f"d{r} holds an unevaluated assembler symbol and was read")
        return self.d[r]

    def read(self, arg, bits):
        if arg.startswith("#"):
            return _num(arg[1:]) & ((1 << bits) - 1)
        if re.fullmatch(r"d[0-7]", arg):
            return self._dreg(int(arg[1]), bits) & ((1 << bits) - 1)
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

    def _store(self, reg, off, bits, val, line, loop):
        if reg not in self.bufs:
            raise ClipScrollError(f"store into {reg}, which this model does not collect")
        words = [(val >> 16) & 0xFFFF, val & 0xFFFF] if bits == 32 else [val]
        for k, w in enumerate(words):
            self.bufs[reg][off + 2 * k] = w
            self.writer[(reg, off + 2 * k)] = line
            if reg == "Horiz_Scroll_Buf":
                self.loop_of[off + 2 * k] = loop

    def write(self, arg, bits, val, line, loop):
        val &= (1 << bits) - 1
        m = re.fullmatch(r"d([0-7])", arg)
        if m:
            r = int(m.group(1))
            mask = (1 << bits) - 1
            self.d[r] = ((self.d[r] & ~mask) | val) & 0xFFFFFFFF
            if bits == 32:
                self.poison.pop(r, None)
            elif bits == 16 and r in self.poison:
                self.poison[r].discard("lo")
            return
        m = re.fullmatch(r"\(a([0-7])\)\+", arg)
        if m:
            reg, off = self.a[int(m.group(1))]
            self._store(reg, off, bits, val, line, loop)
            self.a[int(m.group(1))] = (reg, off + bits // 8)
            return
        m = re.fullmatch(r"-\(a([0-7])\)", arg)
        if m:
            reg, off = self.a[int(m.group(1))]
            off -= bits // 8
            self._store(reg, off, bits, val, line, loop)
            self.a[int(m.group(1))] = (reg, off)
            return
        ref = self._mem_ref(arg)
        if ref and not ref[1]:
            self.mem[ref[0]] = val
            return
        raise ClipScrollError(f"unsupported destination operand `{arg}`")

    def _flags(self, v, bits, carry=False):
        v &= (1 << bits) - 1
        self.z = v == 0
        self.n = bool(v >> (bits - 1))
        self.c = carry

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
                if not self.stack:
                    return
                nxt = self.stack.pop()
            elif base == "addq" and ops[1] == "sp":
                if _num(ops[0][1:]) != 4 or not self.stack:
                    raise ClipScrollError(f"s2.asm:{line}: `{op} {args}` is not a caller pop")
                self.stack.pop()                      # drop the return address
            elif base == "bsr":
                tgt = ops[0]
                if tgt in self.stubs:
                    pass
                else:
                    self.stack.append(nxt)
                    nxt = self._target(pc, tgt)
            elif base == "tst":
                v = self.read(ops[0], bits)
                self._flags(v, bits)
            elif base in ("bne", "beq", "bra", "bmi", "bpl", "bcc", "bcs", "bhs", "blo"):
                take = {"bra": True, "bne": not self.z, "beq": self.z, "bmi": self.n,
                        "bpl": not self.n, "bcc": not self.c, "bhs": not self.c,
                        "bcs": self.c, "blo": self.c}[base]
                if take:
                    if base == "bra" and ops[0] in self.stop_at:
                        self.stopped = ops[0]
                        return
                    nxt = self._target(pc, ops[0])
            elif base == "dbf":
                r = int(ops[0][1])
                c = (self._dreg(r, 16) - 1) & 0xFFFF
                self.d[r] = (self.d[r] & 0xFFFF0000) | c
                if c != 0xFFFF:
                    nxt = self._target(pc, ops[1])
            elif base == "move":
                v = self.read(ops[0], bits)
                self.write(ops[1], bits, v, line, loop)
                self._flags(v, bits)
            elif base == "moveq":
                r = int(ops[1][1])
                try:
                    self.d[r] = _sx(_num(ops[0][1:]), 8) & 0xFFFFFFFF
                    self.poison.pop(r, None)
                except _Symbolic:
                    self.poison[r] = {"lo", "hi"}
            elif base == "lea":
                self.a[int(ops[1][1])] = self._ea(ops[0])
            elif base == "adda":
                r = int(ops[1][1])
                reg, off = self.a[r]
                self.a[r] = (reg, off + _sx(self.read(ops[0], bits), bits))
            elif base == "neg":
                v = -self.read(ops[0], bits)
                self.write(ops[0], bits, v, line, loop)
                self._flags(v, bits)
            elif base == "swap":
                r = int(ops[0][1])
                self.d[r] = ((self._dreg(r) << 16) | (self.d[r] >> 16)) & 0xFFFFFFFF
            elif base == "ext":
                r = int(ops[0][1])
                if bits == 16:
                    self.write(ops[0], 16, _sx(self._dreg(r, 16), 8), line, loop)
                else:
                    self.d[r] = _sx(self._dreg(r, 16), 16) & 0xFFFFFFFF
                    self.poison.pop(r, None)
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
                self._flags(v, bits)
            elif base in ("add", "sub", "subq", "addq", "subi", "addi"):
                a_ = self.read(ops[0], bits)
                b_ = self.read(ops[1], bits)
                if base in ("add", "addq", "addi"):
                    v = b_ + a_
                    carry = v >> bits != 0
                else:
                    v = b_ - a_
                    carry = a_ > b_                   # unsigned borrow
                self.write(ops[1], bits, v, line, loop)
                self._flags(v, bits, carry)
            elif base == "andi":
                v = self.read(ops[1], bits) & self.read(ops[0], bits)
                self.write(ops[1], bits, v, line, loop)
                self._flags(v, bits)
            elif base == "divs":
                src = _sx(self.read(ops[0], 16), 16)
                r = int(ops[1][1])
                num = _sx(self._dreg(r), 32)
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
        m = re.fullmatch(r"\((\w+)\+([^)]+)\)\.[wl]", arg)
        if m:
            return (m.group(1), _num(m.group(2)))
        m = re.fullmatch(r"(\w+)\(pc\)", arg)
        if m:
            if m.group(1) not in self.tables:
                raise ClipScrollError(f"lea onto `{m.group(1)}`, a table this model does not hold")
            return (m.group(1), 0)
        m = re.fullmatch(r"\(a([0-7]),d([0-7])\.w\)", arg)
        if m:
            reg, off = self.a[int(m.group(1))]
            return (reg, off + _sx(self._dreg(int(m.group(2)), 16), 16))
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


# ---------------------------------------------------------------------------
# METROPOLIS — read SwScrl_MTZ / InitCam_Std (woven first screen s2_mtz_cpz, 2026-09-27)
# ---------------------------------------------------------------------------
#
# Why it exists: with no transcription Metropolis kept the ACT DEFAULT scroll, and a crossing
# into it lerped the background back to that config for PARALLAX_TRANS_DEFAULT frames past the
# tunnel's mouth (crossing_witness, MEASURED on s2_mtz_cpz: 13-16 "mid-lerp" glitch ticks per
# arrival), because the snap is a property of the SCENE entered and the act default has none.

def derive_mtz(text, paste_dy):
    """Metropolis's scene: ONE flat band, exact. SwScrl_MTZ ("just a duplicate of
    SwScrl_Minimal") writes the same BG word to all 224 lines; InitCam_Index names InitCam_Std
    for MTZ1,2, which sets BG_Y = camY >> 2 and BG_X = camX >> 3, cross-checked against
    SwScrl_MTZ's per-frame `asl.l` rates the way CPZ's are."""
    lines = _lines(text)

    def find(pattern, body, what, off, flags=0):
        m = re.search(pattern, body, flags)
        if not m:
            raise ClipScrollError(f"MTZ: {what} not found in s2.asm (pattern {pattern!r})")
        return m, off + body[:m.start()].count("\n") + 1

    find(r"^InitCam_Index:[^\n]*\n(?:[^\n]*\n){0,8}?\s*zoneOffsetTableEntry\.w\s+InitCam_Std\s*;\s*MTZ1,2",
         text, "InitCam_Index's MTZ1,2 entry naming InitCam_Std", 0, re.M)
    s, e = _span(lines, "InitCam_Std", "the standard camera init")
    init = "\n".join(lines[s:e])
    m_i, ln_i = find(r"asr\.w\s+#(\d+),d0\s*\n\s*move\.w\s+d0,\(Camera_BG_Y_pos\)\.w\s*\n"
                     r"\s*asr\.w\s+#(\d+),d1\s*\n\s*move\.w\s+d1,\(Camera_BG_X_pos\)\.w",
                     init, "InitCam_Std's BG Y / BG X shifts", s)
    v_shift, x_shift = int(m_i.group(1)), int(m_i.group(2))
    s2_, e2 = _span(lines, "SwScrl_MTZ", "Metropolis's scroll routine")
    body = "\n".join(lines[s2_:e2])
    m_r, ln_r = find(r"move\.w\s+\(Camera_X_pos_diff\)\.w,d4\s*\n\s*ext\.l\s+d4\s*\n\s*asl\.l\s+#(\d+),d4"
                     r"\s*\n\s*move\.w\s+\(Camera_Y_pos_diff\)\.w,d5\s*\n\s*ext\.l\s+d5\s*\n\s*asl\.l\s+#(\d+),d5"
                     r"\s*\n\s*bsr\.w\s+SetHorizVertiScrollFlagsBG", body, "SwScrl_MTZ's BG rates", s2_)
    rates = (8 - int(m_r.group(1)), 8 - int(m_r.group(2)))
    if rates != (x_shift, v_shift):
        raise ClipScrollError(f"MTZ: InitCam_Std's shifts (BG X {x_shift}, BG Y {v_shift}) "
                              f"disagree with SwScrl_MTZ's per-frame rates {rates}")
    m_l, ln_l = find(r"move\.w\s+#224-1,d1\s*\n\s*move\.w\s+\(Camera_X_pos\)\.w,d0\s*\n\s*neg\.w\s+d0"
                     r"\s*\n\s*swap\s+d0\s*\n\s*move\.w\s+\(Camera_BG_X_pos\)\.w,d0\s*\n\s*neg\.w\s+d0"
                     r"\s*\n\s*\n?-\s*move\.l\s+d0,\(a1\)\+\s*\n\s*dbf\s+d1,-", body,
                     "SwScrl_MTZ's one-value store over all 224 lines", s2_)
    bands = [{"kind": "flat", "plane_top": 0, "ratio": Fraction(1, 1 << x_shift),
              "src": [ln_i, ln_l], "phase": 0}]
    bands[0]["factor"] = encode_factor(bands[0]["ratio"])
    bands[0]["top"] = 0
    bands[0]["engine_end"] = PLANE_LINES
    return {"zone": "MTZ", "routine": "SwScrl_MTZ", "v_factor": v_shift, "v_center": paste_dy,
            "v_offset": 0, "bands": bands,
            "provenance": {"InitCam_Std": ln_i, "SwScrl_MTZ rates": ln_r,
                           "SwScrl_MTZ store": ln_l}}


# ---------------------------------------------------------------------------
# Shared by the BG-ROW-keyed zones added for the woven act (OOZ, HPZ, WFZ, 2026-09-27)
# ---------------------------------------------------------------------------
#
# These three key their bands by BACKGROUND ROW (the row of the BG map a screen line shows),
# the way CPZ does, so a band is a plane-line band. Each raw deriver describes Sonic 2's own
# background in BG-row space ({row: kind}) and its vertical map (v_factor, and the BG row at
# donor camera Y 0 as `v_offset`); `_finish_plane` then cuts the 512-line plane window the
# lowering chose (`clip_bg_lower.window_top`, r0) out of it.

def nearest_factor(r):
    """(factor, exact) — r encoded exactly when the engine can, else the expressible ratio
    nearest to it (ties to the smaller). Used ONLY where a Sonic 2 ratio has no 2^-a +- 2^-b
    form (Hidden Palace's ramp); the spec records every such band and its error."""
    try:
        return encode_factor(r), True
    except ClipScrollError:
        pass
    best = None
    for s1 in range(15):
        for s2 in [LOCKED] + list(range(s1 + 1, 15)):
            for op in ((0,) if s2 == LOCKED else (0, 1)):
                v = factor_value(s1, s2, op)
                key = (abs(v - r), v)
                if best is None or key < best[0]:
                    best = (key, (s1, s2, op))
    return encode_factor(factor_value(*best[1])), False


def _finish_plane(kinds, v_factor, v_offset, r0, lo_seen, what):
    """Bands over plane lines [.., 512) from {bg_row: kind} for rows r0 .. r0 + 511.

    `kind` is ("flat", ratio), ("ripple", ratio) or ("drift", rate). Rows the
    source never puts on screen (below `lo_seen`, the lowest BG row any camera Y reaches) take
    the first seen row's kind: they are never visible, and a band must start the plane. The
    first band's top is the lowest REACHABLE plane line, max(0, lo_seen - r0): scene_dsl maps a
    top back to a world Y through v_center, and a line no camera reaches has no world Y."""
    first_seen = min(k for k in kinds if k >= lo_seen)
    lo = max(0, lo_seen - r0)
    rows = []
    for pl in range(lo, PLANE_LINES):
        bg = pl + r0
        k = kinds.get(bg if bg >= lo_seen else first_seen)
        if k is None:
            raise ClipScrollError(f"{what}: background row {bg} (plane line {pl}) is inside the "
                                  f"plane window {r0}..{r0 + PLANE_LINES - 1} and the source "
                                  f"never scrolls it")
        rows.append((pl, k))
    bands = []
    for pl, k in rows:
        if bands and bands[-1]["_key"] == k:
            continue
        b = {"_key": k, "plane_top": pl, "top": pl, "phase": 0}
        if k[0] == "drift":
            b.update(kind="flat", ratio=Fraction(0), drift=k[1])
        else:
            b.update(kind=k[0], ratio=k[1])
        bands.append(b)
    if len(bands) > MAX_BANDS:
        raise ClipScrollError(f"{what} needs {len(bands)} bands in its plane window; the engine "
                              f"holds {MAX_BANDS}")
    approx = []
    for k, b in enumerate(bands):
        b["factor"], exact = nearest_factor(b["ratio"])
        if not exact:
            got = factor_value(*b["factor"])
            approx.append({"plane_top": b["plane_top"], "s2_ratio": b["ratio"], "engine": got})
            b["s2_ratio"] = b["ratio"]
            b["ratio"] = got
        b["engine_end"] = bands[k + 1]["plane_top"] if k + 1 < len(bands) else PLANE_LINES
        b.pop("_key")
    return bands, v_offset - r0, approx


def _prog_between(lines, label, end_pat, what, fixbugs):
    """A routine's instructions from `label:` to the first line matching end_pat (inclusive),
    for sources whose routines hold column-0 `loc_XXXX:` labels (the prototype's)."""
    start = next((i for i, ln in enumerate(lines) if re.match(rf"^{re.escape(label)}:", ln)), None)
    if start is None:
        raise ClipScrollError(f"the donor has no `{label}:` ({what})")
    end = next((i for i in range(start + 1, len(lines)) if re.search(end_pat, lines[i])), None)
    if end is None:
        raise ClipScrollError(f"`{label}:` has no line matching {end_pat!r} ({what})")
    return _assemble(lines, start + 1, end + 1, fixbugs), start + 1


# ---------------------------------------------------------------------------
# OIL OCEAN — run SwScrl_OOZ
# ---------------------------------------------------------------------------
#
# SwScrl_OOZ writes Horiz_Scroll_Buf BOTTOM UP through local line helpers (`bsr .doLines`, and
# a helper that pops its caller with `addq.l #4,sp` when the 224 lines run out). It is RUN, at
# two power-of-two camera X values and at two BG Y values so that every background row from
# the lowest reachable (InitCam_OOZ's + $50) to the plane's last is on screen in one of them.
# Each row's word gives its ratio; the ripple rows are the ones whose word moves when the
# ripple data does; each ripple row's TABLE INDEX is read by running with a ramp table, which
# is how the sun's direction (bottom up, so the index DEcreases down the screen) is derived.

OOZ_STUBS = ("SetVertiScrollFlagsBG2", "SetHorizVertiScrollFlagsBG")


def _ooz_run(prog, tables, camx, bgx, bgy):
    m = _Machine(prog, {"Camera_X_pos": camx & 0xFFFF, "Camera_BG_X_pos": bgx & 0xFFFF,
                        "Camera_BG_Y_pos": bgy, "Camera_X_pos_diff": 0, "Camera_Y_pos_diff": 0,
                        "Vscroll_Factor_BG": 0, "Vint_runcount": 1, "TempArray_LayerDef": 0},
                 tables, stubs=OOZ_STUBS)
    m.a[1] = None
    m.run()
    out = {}
    for line in range(SCREEN_LINES):
        off = line * 4
        if off not in m.buf or off + 2 not in m.buf:
            raise ClipScrollError(f"SwScrl_OOZ left screen line {line} unwritten at BG Y {bgy}")
        if _sx(m.buf[off], 16) != -_sx(camx, 16):
            raise ClipScrollError(f"SwScrl_OOZ line {line}: the foreground word is not -camX")
        out[bgy + line] = _sx(m.buf[off + 2], 16)
    if any(k >= SCREEN_LINES * 4 or k < 0 for k in m.buf):
        raise ClipScrollError("SwScrl_OOZ wrote outside the 224-line scroll buffer")
    return out


def derive_ooz_raw(text):
    lines = _lines(text)
    fb = _fixbugs(lines)
    s, e = _span(lines, "InitCam_OOZ", "Oil Ocean's camera init")
    init = "\n".join(lines[s:e])
    m_i = re.search(r"lsr\.w\s+#(\d+),d0\s*\n\s*addi\.w\s+#\$([0-9A-Fa-f]+),d0\s*\n\s*"
                    r"move\.w\s+d0,\(Camera_BG_Y_pos\)\.w\s*\n\s*clr\.l\s+\(Camera_BG_X_pos\)\.w",
                    init)
    if not m_i:
        raise ClipScrollError("OOZ: InitCam_OOZ is not `lsr.w #n,d0 / addi.w #$k,d0 / BG_Y / "
                              "clr.l BG_X`")
    v_shift, v_add = int(m_i.group(1)), int(m_i.group(2), 16)
    ln_i = s + init[:m_i.start()].count("\n") + 1
    s2_, e2 = _span(lines, "SwScrl_OOZ", "Oil Ocean's scroll routine")
    prog = _assemble(lines, s2_, e2, fb)
    body = "\n".join(f"{op} {a}" for _l, _lb, op, a in prog if op)
    m_x = re.search(r"move\.w \(Camera_X_pos_diff\)\.w,(d\d)\next\.l \1\nasl\.l #(\d+),\1\n"
                    r"add\.l \1,\(Camera_BG_X_pos\)\.w", body)
    m_y = re.search(r"move\.w \(Camera_Y_pos_diff\)\.w,(d\d)\next\.l \1\nasl\.l #(\d+),\1", body)
    if not (m_x and m_y):
        raise ClipScrollError(f"OOZ: SwScrl_OOZ's per-frame BG X / BG Y rates are unreadable at "
                              f"fixBugs {fb}")
    x_shift, y_rate = 8 - int(m_x.group(2)), 8 - int(m_y.group(2))
    if y_rate != v_shift:
        raise ClipScrollError(f"OOZ: InitCam_OOZ's BG Y shift {v_shift} disagrees with "
                              f"SwScrl_OOZ's per-frame rate {y_rate}")
    ripple = _dc_bytes(lines, "SwScrl_RippleData")
    p, cyc = _ripple_cycle(ripple)

    def runs(tab, camx):
        out = {}
        for bgy in (v_add, PLANE_LINES - SCREEN_LINES):
            out.update(_ooz_run(prog, {"SwScrl_RippleData": [v & 0xFF for v in tab]}, camx,
                                camx >> x_shift, bgy))
        return out

    big, half = 8192, 4096
    zero, sixty4 = runs([0] * len(ripple), big), runs([64] * len(ripple), big)
    zero_h = runs([0] * len(ripple), half)
    ramp = runs([i & 0x7F for i in range(len(ripple))], big)
    kinds = {}
    for row in sorted(zero):
        r_big, r_half = Fraction(-zero[row], big), Fraction(-zero_h[row], half)
        if r_big != r_half:
            raise ClipScrollError(f"OOZ background row {row}: {r_big} of camX at {big} but "
                                  f"{r_half} at {half}; not one ratio")
        if sixty4[row] - zero[row] == 64:
            idx = ramp[row] - zero[row]
            kinds[row] = ("ripple", r_big, idx)
        elif sixty4[row] != zero[row]:
            raise ClipScrollError(f"OOZ background row {row} moves with the ripple data by "
                                  f"{sixty4[row] - zero[row]}, not by the entry")
        else:
            kinds[row] = ("flat", r_big)
    # the ripple rows' index must be one straight run (the sun), and its direction is DERIVED
    rip = sorted(r for r, k in kinds.items() if k[0] == "ripple")
    if rip:
        steps = {kinds[b][2] - kinds[a][2] for a, b in zip(rip, rip[1:])}
        if len(steps) != 1 or steps.pop() not in (1, -1) or rip != list(range(rip[0], rip[-1] + 1)):
            raise ClipScrollError("OOZ: the ripple rows are not one run reading consecutive entries")
        direction = kinds[rip[1]][2] - kinds[rip[0]][2] if len(rip) > 1 else 1
        # S2's entry at BG row r is R[a + direction * r]; `a` is that line's extrapolation to
        # row 0. The engine reads T[(phase + plane line) & 255] (derive_ooz sets phase).
        if direction == 1:
            table = [_sx(cyc[i % p], 8) for i in range(DEFORM_TABLE_LEN)]
        else:
            table = [_sx(cyc[(-i) % p], 8) for i in range(DEFORM_TABLE_LEN)]
        base = kinds[rip[0]][2] - direction * rip[0]
        for r in rip:
            kinds[r] = ("ripple", kinds[r][1])
    else:
        table, direction, base = None, 0, 0
    return {"zone": "OOZ", "routine": "SwScrl_OOZ", "kinds": kinds, "v_factor": v_shift,
            "v_offset": v_add, "lo_seen": v_add, "ripple_phase": base,
            "ripple_direction": direction, "deform_table": table, "ripple_cycle": p,
            "x_shift": x_shift,
            "provenance": {"InitCam_OOZ": ln_i, "SwScrl_OOZ": s2_,
                           "SwScrl_RippleData": _span(lines, "SwScrl_RippleData", "")[0]}}


def derive_ooz(text, paste_dy, r0=0):
    """Oil Ocean's scene, DERIVED BY RUNNING SwScrl_OOZ (see the block above). Exact ratios
    (camX/8 empty sky and factory, camX/32 / 64 / 128 cloud rows); the sun's heat haze is the
    ripple table read backwards, static (the EHZ ripple's standing rule). BG_X starts at 0 in
    Sonic 2 (InitCam_OOZ clears it) and advances at camX/8: the engine's camX/8 differs from it
    by a constant horizontal phase, which on a repeating background is invisible."""
    raw = derive_ooz_raw(text)
    bands, v_off, approx = _finish_plane(raw["kinds"], raw["v_factor"], raw["v_offset"], r0,
                                         raw["lo_seen"], "Oil Ocean")
    # forward (T[k] = R[k]):  T[phase + pl] = R[a + pl + r0]  ->  phase = a + r0
    # reversed (T[k] = R[-k]): T[phase + pl] = R[a - pl - r0]  ->  phase = r0 - a
    p = raw["ripple_cycle"]
    for b in bands:
        if b["kind"] == "ripple":
            a = raw["ripple_phase"]
            b["phase"] = ((a + r0) if raw["ripple_direction"] == 1 else (r0 - a)) % p
    spec = {"zone": "OOZ", "routine": "SwScrl_OOZ", "v_factor": raw["v_factor"],
            "v_center": paste_dy, "v_offset": v_off, "bands": bands, "window_top": r0,
            "approximations": approx, "provenance": raw["provenance"]}
    if raw["deform_table"] is not None:
        spec["deform_table"] = raw["deform_table"]
        spec["ripple_cycle"] = raw["ripple_cycle"]
        spec["table_label"] = TABLE_LABEL if raw["ripple_direction"] == 1 else TABLE_LABEL + "_Rev"
    return spec



# ---------------------------------------------------------------------------
# HIDDEN PALACE — the PROTOTYPE's Bg_Scroll_HPz, half run and half read
# ---------------------------------------------------------------------------
#
# Hidden Palace's only donor is the Simon Wai prototype, so its scroll is the PROTOTYPE's
# (main.asm), the one written for this background. Bg_Scroll_HPz builds a table of one BG X
# word per 16-line BLOCK of the background in TempArray_LayerDef (a top band at camX/2, a
# four-step ramp down to BG_X, BG_X = camX/4 across the middle, the ramp mirrored, camX/2 at
# the bottom), then branches to the shared writer loc_6AA8, which puts block (BG row / 16) on
# every screen line. The TABLE HALF IS RUN (the interpreter, two power-of-two camera X values);
# the WRITER IS READ by pattern (a computed `jmp` into sixteen unrolled stores is outside the
# subset): its block height (16 stores, `andi.w #$F`) and the table index (BG_Y & $3F0) >> 3.
#
# THE ONE APPROXIMATION, MEASURED BY THE SPEC: the ramp's four ratios are 57/128, 50/128,
# 43/128 and 36/128 of camX (camX/2 minus 7*camX/128 a step). 36/128 = 1/4 + 1/32 is exact;
# the other three have no 2^-a +- 2^-b form, so each takes the nearest the engine can decode
# (`nearest_factor`) and is listed in spec["approximations"] with both ratios.

HPZ_STUBS = ("Scroll_Block2", "Scroll_Block3")


def _proto_zone_row(lines, table, zone_id, what):
    """The label a prototype zoneOrderedOffsetTable row names for zone_id."""
    s, _e = next(((i + 1, 0) for i, ln in enumerate(lines)
                  if re.match(rf"^{table}:\s*zoneOrderedOffsetTable\s+2,\s*1", ln)), (None, 0))
    if s is None:
        raise ClipScrollError(f"the prototype has no `{table}: zoneOrderedOffsetTable 2,1` ({what})")
    rows = []
    for ln in lines[s:]:
        m = re.match(r"^\s*zoneOffsetTableEntry\.w\s+(\w+)", ln)
        if m:
            rows.append(m.group(1))
        elif re.match(r"^\s*zoneTableEnd", ln):
            break
    if len(rows) <= zone_id:
        raise ClipScrollError(f"{table} has {len(rows)} rows; zone ${zone_id:02X} is past it")
    return rows[zone_id]


def derive_hpz_raw(text, zone_id=None):
    import s2_donor as sd
    zone_id = sd.zone_row("HPZ", sd.S2_PROTOTYPE)["zone_id"] if zone_id is None else zone_id
    lines = _lines(text)
    fb = _fixbugs(lines)
    init_label = _proto_zone_row(lines, "InitCam_Index", zone_id, "the camera-init table")
    scroll_label = _proto_zone_row(lines, "Bg_Scroll_Index", zone_id, "the BG scroll table")
    start = next((i for i, ln in enumerate(lines) if re.match(rf"^{init_label}:", ln)), None)
    if start is None:
        raise ClipScrollError(f"HPZ: no `{init_label}:`")
    init = "\n".join(lines[start + 1:start + 5])
    m_i = re.search(r"asr\.w\s+#(\d+),d0\s*\n\s*move\.w\s+d0,\(Camera_BG_Y_pos\)\.w\s*\n\s*"
                    r"clr\.l\s+\(Camera_BG_X_pos\)\.w", init)
    if not m_i:
        raise ClipScrollError(f"HPZ: {init_label} is not `asr.w #n,d0 / BG_Y / clr.l BG_X`")
    v_shift = int(m_i.group(1))
    prog, s0 = _prog_between(lines, scroll_label, r"^\s*bra\.w\s+loc_6AA8\b",
                             "Hidden Palace's BG scroll", fb)
    body = "\n".join(f"{op} {a}" for _l, _lb, op, a in prog if op)
    m_r = re.search(r"move\.w \(Camera_X_pos_diff\)\.w,d4\next\.l d4\nasl\.l #(\d+),d4\n"
                    r"moveq #\d+,d6\nbsr\.w Scroll_Block2\nmove\.w \(Camera_Y_pos_diff\)\.w,d5\n"
                    r"ext\.l d5\nasl\.l #(\d+),d5\nmoveq #\d+,d6\nbsr\.w Scroll_Block3", body)
    if not m_r:
        raise ClipScrollError("HPZ: Bg_Scroll_HPz's per-frame BG X / BG Y rates are unreadable")
    x_shift, y_rate = 8 - int(m_r.group(1)), 8 - int(m_r.group(2))
    if y_rate != v_shift:
        raise ClipScrollError(f"HPZ: {init_label}'s BG Y shift {v_shift} disagrees with the "
                              f"per-frame rate {y_rate}")
    m_w = re.search(r"lea \(TempArray_LayerDef\)\.w,a2\nmove\.w \(Camera_BG_Y_pos\)\.w,d0\n"
                    r"move\.w d0,d2\nandi\.w #\$([0-9A-Fa-f]+),d0\nlsr\.w #(\d+),d0\n"
                    r"lea \(a2,d0\.w\),a2\nbra\.w loc_6AA8$", body)
    if not m_w:
        raise ClipScrollError("HPZ: Bg_Scroll_HPz's hand-off to loc_6AA8 (the table index) is "
                              "unreadable")
    index_mask, index_shift = int(m_w.group(1), 16), int(m_w.group(2))
    # the writer, READ: `andi.w #$F,d2` / `jmp loc_6AC6(pc,d2.w)` / 16 x `move.l d0,(a1)+`
    ws = next((i for i, ln in enumerate(lines) if re.match(r"^loc_6AA8:", ln)), None)
    wtxt = "\n".join(lines[ws:ws + 40]) if ws is not None else ""
    m_j = re.search(r"andi\.w\s+#\$F,d2\s*\n\s*add\.w\s+d2,d2\s*\n\s*move\.w\s+\(a2\)\+,d0\s*\n"
                    r"\s*jmp\s+loc_6AC6\(pc,d2\.w\)\s*\nloc_6AC4:\s*\n\s*move\.w\s+\(a2\)\+,d0\s*\n"
                    r"loc_6AC6:\s*\n((?:\s*move\.l\s+d0,\(a1\)\+\s*\n)+)\s*dbf\s+d1,loc_6AC4", wtxt)
    if not m_j:
        raise ClipScrollError("HPZ: the shared writer loc_6AA8 is not the 16-line block writer "
                              "this reads it as")
    block = m_j.group(1).count("move.l")
    if block != 16 or (index_mask >> index_shift) << index_shift != index_mask or \
            (1 << (index_shift + 1)) != block:
        raise ClipScrollError(f"HPZ: block {block} lines, index mask ${index_mask:X} >> "
                              f"{index_shift}: the table does not index 2-byte words per block")
    wrap = (index_mask | (block - 1)) + 1                  # BG rows before the index wraps

    def run(camx):
        m = _Machine(prog, {"Camera_X_pos": camx & 0xFFFF, "Camera_BG_X_pos": (camx >> x_shift),
                            "Camera_BG_Y_pos": 0, "Camera_X_pos_diff": 0, "Camera_Y_pos_diff": 0,
                            "Vscroll_Factor_BG": 0},
                     {}, stubs=HPZ_STUBS, stop_at=("loc_6AA8",),
                     regions=("TempArray_LayerDef",))
        m.run()
        if m.stopped != "loc_6AA8":
            raise ClipScrollError("HPZ: Bg_Scroll_HPz did not reach its writer")
        tab = m.bufs["TempArray_LayerDef"]
        n = max(tab) // 2 + 1
        if sorted(tab) != list(range(0, 2 * n, 2)):
            raise ClipScrollError("HPZ: the block table has holes")
        return [_sx(tab[2 * k], 16) for k in range(n)]

    big, half = 8192, 4096
    tb, th = run(big), run(half)
    kinds = {}
    for k, (vb, vh) in enumerate(zip(tb, th)):
        rb, rh = Fraction(-vb, big), Fraction(-vh, half)
        if rb != rh:
            raise ClipScrollError(f"HPZ block {k}: {rb} of camX at {big}, {rh} at {half}")
        for row in range(k * block, (k + 1) * block):
            kinds[row] = ("flat", rb)
    return {"zone": "HPZ", "routine": scroll_label, "kinds": kinds, "v_factor": v_shift,
            "v_offset": 0, "lo_seen": 0, "blocks": len(tb), "block": block, "wrap": wrap,
            "x_shift": x_shift,
            "provenance": {init_label: start + 1, scroll_label: s0, "loc_6AA8": ws + 1}}


def derive_hpz(text, paste_dy, r0=0):
    """Hidden Palace's scene (see the block above). Flat bands keyed by BG row; three of the
    ramp's four ratios approximated to the nearest engine factor, listed in the spec."""
    raw = derive_hpz_raw(text)
    if r0 + PLANE_LINES > raw["wrap"]:
        raise ClipScrollError(f"HPZ: the plane window {r0}..{r0 + PLANE_LINES - 1} passes the "
                              f"writer's {raw['wrap']}-row index wrap")
    bands, v_off, approx = _finish_plane(raw["kinds"], raw["v_factor"], raw["v_offset"], r0,
                                         raw["lo_seen"], "Hidden Palace")
    return {"zone": "HPZ", "routine": raw["routine"], "v_factor": raw["v_factor"],
            "v_center": paste_dy, "v_offset": v_off, "bands": bands, "window_top": r0,
            "approximations": approx, "blocks": raw["blocks"], "block": raw["block"],
            "provenance": raw["provenance"]}


# ---------------------------------------------------------------------------
# WING FORTRESS — read SwScrl_WFZ, its segment arrays and LevEvents_WFZ
# ---------------------------------------------------------------------------
#
# Wing Fortress has no camera init (InitCam_Index names InitCam_Null1, an rts). Its background
# position is set by the level events: LevEvents_WFZ_Routine1 copies the camera into
# Camera_BG_X/Y_pos and zeroes the offsets, and Routine2 (every frame until the camera passes
# the routine-3 thresholds) hands the camera to ScrollBG, which moves the BG toward
# camera - offset. So in normal play the background is the camera, 1:1, on both axes.
#
# SwScrl_WFZ keys its bands by BACKGROUND ROW through a segment array of (line count, index)
# pairs, the index picking a TempArray_LayerDef long: 0 and 4 are Camera_BG_X_pos (1:1), and
# 8 / $C / $10 are three accumulators that `addi.l` adds $8000 / $4000 / $2000 to every frame
# and that nothing else moves. Sonic 2's own comment calls it a bug ("this tallies only the
# cloud speeds"): THE CLOUD ROWS IGNORE THE CAMERA and only drift. That is what is transcribed
# (a factor-0 layer with SceneDrift.Rate), because the brief is Sonic 2's behaviour. Two
# arrays exist (Transition past camera X $2700, Normal before it); the plane window must read
# the same index from both, or it is refused.

def _wfz_segments(lines, label, fb):
    s, e = _span(lines, label, "a WFZ BG segment array")
    prog = _assemble(lines, s, e, fb)
    vals = []
    for _l, _lb, op, args in prog:
        if op == "dc.b":
            vals.extend(_num(v) for v in args.split(","))
        elif op not in (None, "even"):
            break
    if len(vals) % 2:
        raise ClipScrollError(f"{label} holds an odd number of bytes")
    return list(zip(vals[0::2], vals[1::2]))


def derive_wfz_raw(text):
    lines = _lines(text)
    fb = _fixbugs(lines)
    if not re.search(r"^InitCam_Index:[^\n]*\n(?:[^\n]*\n){0,10}?\s*zoneOffsetTableEntry\.w\s+"
                     r"InitCam_Null1\s*;\s*WFZ", text, re.M):
        raise ClipScrollError("WFZ: InitCam_Index's WFZ row does not name InitCam_Null1")
    s1, e1 = _span(lines, "LevEvents_WFZ_Routine1", "WFZ's first level event")
    r1 = "\n".join(lines[s1:e1])
    if not re.search(r"move\.l\s+\(Camera_X_pos\)\.w,\(Camera_BG_X_pos\)\.w\s*\n\s*"
                     r"move\.l\s+\(Camera_Y_pos\)\.w,\(Camera_BG_Y_pos\)\.w", r1) or not \
            re.search(r"move\.w\s+d0,\(Camera_BG_X_offset\)\.w\s*\n\s*move\.w\s+d0,"
                      r"\(Camera_BG_Y_offset\)\.w", r1):
        raise ClipScrollError("WFZ: LevEvents_WFZ_Routine1 does not copy the camera into the BG "
                              "and zero the BG offsets")
    s2, e2 = _span(lines, "LevEvents_WFZ_Routine2", "WFZ's normal-play level event")
    r2 = "\n".join(lines[s2:e2])
    m_t = re.search(r"cmpi\.w\s+#\$([0-9A-Fa-f]+),\(Camera_X_pos\)\.w\s*\n\s*blo\.s\s+\+\s*\n\s*"
                    r"cmpi\.w\s+#\$([0-9A-Fa-f]+),\(Camera_Y_pos\)\.w", r2)
    if not m_t or not re.search(r"move\.w\s+\(Camera_X_pos\)\.w,d0\s*\n\s*move\.w\s+"
                                r"\(Camera_Y_pos\)\.w,d1\s*\n\s*bra\.w\s+ScrollBG", r2):
        raise ClipScrollError("WFZ: LevEvents_WFZ_Routine2 is not the camera -> ScrollBG hand-off")
    s3, e3 = _span(lines, "ScrollBG", "the BG follower")
    sb = "\n".join(lines[s3:e3])
    if not re.search(r"sub\.w\s+\(Camera_BG_X_pos\)\.w,d0\s*\n\s*sub\.w\s+\(Camera_BG_X_offset\)"
                     r"\.w,d0", sb) or not re.search(r"sub\.w\s+\(Camera_BG_Y_pos\)\.w,d1\s*\n\s*"
                                                   r"sub\.w\s+\(Camera_BG_Y_offset\)\.w,d1", sb):
        raise ClipScrollError("WFZ: ScrollBG does not move the BG toward camera - offset")
    s4, e4 = _span(lines, "SwScrl_WFZ", "Wing Fortress's scroll routine")
    prog = _assemble(lines, s4, e4, fb)
    body = "\n".join(f"{op} {a}" for _l, _lb, op, a in prog if op)
    m_l = re.search(r"lea \(TempArray_LayerDef\)\.w,a2\nmove\.l d0,\(a2\)\+\nmove\.l d1,\(a2\)\+\n"
                    r"addi\.l #\$([0-9A-Fa-f]+),\(a2\)\+\naddi\.l #\$([0-9A-Fa-f]+),\(a2\)\+\n"
                    r"addi\.l #\$([0-9A-Fa-f]+),\(a2\)\+\n", body)
    m_d = re.search(r"move\.l \(Camera_BG_X_pos\)\.w,d0\nmove\.l d0,d1\n", body)
    m_a = re.search(r"lea \(SwScrl_WFZ_Transition_Array\)\.l,a3\ncmpi\.w #\$([0-9A-Fa-f]+),"
                    r"\(Camera_X_pos\)\.w\nbhs\.s \.got_array\nlea \(SwScrl_WFZ_Normal_Array\)\.l,a3",
                    body)
    m_y = re.search(r"move\.w \(Camera_BG_Y_pos\)\.w,d1\nandi\.w #\$([0-9A-Fa-f]+),d1", body)
    if not (m_l and m_d and m_a and m_y):
        raise ClipScrollError("WFZ: SwScrl_WFZ's layer longs, array choice or row index are "
                              "unreadable")
    drift = {8: int(m_l.group(1), 16), 12: int(m_l.group(2), 16), 16: int(m_l.group(3), 16)}
    for idx, v in drift.items():
        if v & 0xFF:
            raise ClipScrollError(f"WFZ: layer ${idx:X}'s 16.16 rate ${v:X} is not a whole "
                                  f"multiple of 1/256 px")
    row_mask = int(m_y.group(1), 16)
    arrays = {nm: _wfz_segments(lines, f"SwScrl_WFZ_{nm}_Array", fb)
              for nm in ("Normal", "Transition")}

    def kinds_of(segs):
        out, row = {}, 0
        for count, idx in segs:
            if idx in (0, 4):
                k = ("flat", Fraction(1))
            elif idx in drift:
                k = ("drift", drift[idx] >> 8)
            else:
                raise ClipScrollError(f"WFZ: segment index ${idx:X} names no layer long")
            for r in range(row, row + count):
                out[r] = k
            row += count
        return out

    return {"zone": "WFZ", "routine": "SwScrl_WFZ", "arrays": {k: kinds_of(v) for k, v in
                                                              arrays.items()},
            "v_factor": 0, "v_offset": 0, "lo_seen": 0, "row_mask": row_mask,
            "transition_x": int(m_a.group(1), 16),
            "routine3_at": (int(m_t.group(1), 16), int(m_t.group(2), 16)),
            "provenance": {"LevEvents_WFZ_Routine1": s1, "LevEvents_WFZ_Routine2": s2,
                           "ScrollBG": s3, "SwScrl_WFZ": s4}}


def derive_wfz(text, paste_dy, r0=0):
    """Wing Fortress's scene: v 1:1 (v_factor 0), and per BG row either the camera 1:1 (the
    static rows) or a factor-0 layer that only DRIFTS (the cloud rows, Sonic 2's own bug). Exact
    in normal play: until the camera passes LevEvents_WFZ_Routine2's thresholds (the getaway-
    ship sequence moves the BG offsets), and inside the plane window the lowering chose."""
    raw = derive_wfz_raw(text)
    if r0 + PLANE_LINES > raw["row_mask"] + 1:
        raise ClipScrollError(f"WFZ: the plane window passes SwScrl_WFZ's row mask "
                              f"${raw['row_mask']:X}")
    nrm, trn = raw["arrays"]["Normal"], raw["arrays"]["Transition"]
    for bg in range(r0, r0 + PLANE_LINES):
        if nrm.get(bg) != trn.get(bg):
            raise ClipScrollError(f"WFZ: background row {bg} scrolls as {nrm.get(bg)} before "
                                  f"camera X ${raw['transition_x']:X} and {trn.get(bg)} after; "
                                  f"one plane window cannot be both")
    bands, v_off, approx = _finish_plane(nrm, raw["v_factor"], raw["v_offset"], r0,
                                         raw["lo_seen"], "Wing Fortress")
    return {"zone": "WFZ", "routine": "SwScrl_WFZ", "v_factor": raw["v_factor"],
            "v_center": paste_dy, "v_offset": v_off, "bands": bands, "window_top": r0,
            "approximations": approx, "exact_until": raw["routine3_at"],
            "provenance": raw["provenance"]}


DERIVERS = {"EHZ": lambda text, dy: derive_ehz(text), "CPZ": derive_cpz, "MTZ": derive_mtz}
#: Zones whose background is lowered through a chosen 512-line WINDOW of a taller map
#: (clip_bg_lower.window_top): their derivers take the window's top row, r0.
WINDOWED = {"OOZ": derive_ooz, "HPZ": derive_hpz, "WFZ": derive_wfz}
#: Which donor each transcription reads: Hidden Palace exists only in the prototype.
DERIVER_DONOR = {"EHZ": "s2disasm", "CPZ": "s2disasm", "MTZ": "s2disasm", "OOZ": "s2disasm",
                 "WFZ": "s2disasm", "HPZ": "s2-simonwai-disasm"}


def derive(donor, zone, paste_dy, r0=None):
    """The spec for one donor zone, or None when this zone has no transcription (the caller
    keeps the act default and says so). `r0` is the top BG row of the plane window the
    lowering uses (default: `clip_bg_lower.window_top`, the rule both halves share)."""
    fn = DERIVERS.get(zone) or WINDOWED.get(zone)
    if fn is None or DERIVER_DONOR.get(zone) != donor:
        return None
    with open(s2_asm_path(donor), "r", errors="replace") as fh:
        text = fh.read()
    if zone in WINDOWED:
        if r0 is None:
            import clip_bg_lower
            r0 = clip_bg_lower.window_top(donor, zone)
        return _nonneg_center(fn(text, paste_dy, r0))
    if r0:
        raise ClipScrollError(f"{zone}'s transcription has no plane window and was asked for "
                              f"one at row {r0}")
    return _nonneg_center(fn(text, paste_dy))


def _nonneg_center(spec):
    """scene() takes v_center as a WORLD Y, 0..32767 (scene_dsl.emp refuses anything else and
    the header field is u16), but the derivers set it to the clip's paste dy, which is
    NEGATIVE for a clip pasted UP (Wing Fortress's woven deck, dy -256: the first build refused
    it). The mapping ((camY - v_center) >> v_factor) + v_offset is unchanged when v_center
    rises by m and v_offset rises by m >> v_factor, EXACTLY, for any m that is a multiple of
    2^v_factor (an arithmetic shift of an integer minus a multiple of the divisor), so fold
    the smallest such m. layer_world_y is unchanged by the same identity."""
    if spec is None or spec["v_factor"] == LOCKED or spec["v_center"] >= 0:
        return spec
    step = 1 << spec["v_factor"]
    m = -(spec["v_center"] // step) * step        # smallest multiple of step >= -v_center
    return dict(spec, v_center=spec["v_center"] + m, v_offset=spec["v_offset"] + (m >> spec["v_factor"]))


def bg_row_at(spec, camy):
    """The BG map row at the top of the screen for DONOR camera Y `camy` (paste_dy 0, no
    window), as Sonic 2 computes it. For clip_bg_lower.window_top."""
    if spec["v_factor"] == LOCKED:
        return spec["v_offset"]
    return (camy >> spec["v_factor"]) + spec["v_offset"]


# ---------------------------------------------------------------------------
# TALL MAPS: the whole reachable height, streamed (WINDOWED-BG-VERTICAL-CLAMP, 2026-09-27)
# ---------------------------------------------------------------------------
#
# A windowed zone (above) lowers ONE 512-line window, and the engine's BG V-scroll then clamps
# to 0..PLANE_CEILING: past it the background stops moving while Sonic 2's keeps scrolling.
# The engine already streams a map TALLER than the plane (regions part 2 step 5):
# `Region.rg_bg_layout` names a row-major blob of any whole number of 64-cell rows,
# `Region.rg_bg_span` is its height, Parallax_Step5_Vscroll clamps against `span - 224`, and
# BG_Stream_Update / Section_RedrawPlanes keep the 64-row ring holding the rows the scroll
# selects (map row m lives in plane row m & 63). So a clip zone whose reachable screen tops
# do not fit one window gets the whole reachable height as ONE tall map instead. Nothing in
# the engine changes: this is data for mechanisms that exist.
#
# WHAT A TALL MAP DOES NOT GIVE FOR FREE: the parallax BAND tops. Step 4a selects a band by
# PLANE line (`vscroll & (PLANE_B_SPAN - 1)`, BG-BAND-PLANE-ANCHOR), so on a taller map two
# map rows 512 lines apart share a band. A zone whose kinds repeat every 512 lines (or whose
# conflicting rows are TRANSPARENT, which no hscroll can show) needs one band layout; Hidden
# Palace's do not (its rows 0..127 take camX/2 and rows 512..639 camX/4). So the zone gets a
# CHAIN of band layouts ("window configs"), each exact for the screen tops it is valid over,
# bound per REGION ROW (`rg_parallax`) and switched where two neighbours are BOTH exact for
# every visible line (the crossing is then invisible whichever frame it lands on). Region
# rows and rg_parallax are existing engine mechanism; the chain is chosen here.
#
# The mapping from camera to map row is the windowed one with the window at R0 (the map's
# first BG row): vscroll = ((camY - v_center) >> v_factor) + v_offset - R0, so every
# identity the windowed path proves (scene_text's world Y, the v_center fold) carries over.

TALL_RAW = {"HPZ": derive_hpz_raw, "WFZ": derive_wfz_raw}
#: A Sonic 2 chunk is 128 lines: the map starts and ends on a chunk row.
CHUNK_LINES = 128
#: The engine's BG_TALL_MAP_MIN_SPAN (engine/level/parallax.emp): one plane plus one row.
TALL_MIN_SPAN = PLANE_LINES + 8
#: VSCROLL_BG_MAX: the act default's ceiling, the one every windowed zone clamps to.
PLANE_CEILING = PLANE_LINES - SCREEN_LINES
#: CAM_SCREEN_HALF_H: a region row is keyed by the camera CENTRE.
CAM_HALF_H = 112
#: The overlap two chained band layouts should share, in screen-top rows: two frames of
#: BG_VSCROLL_MAX_STEP (16), so a scroll trailing its camera by up to 16 rows either side of
#: the switch still shows an exact layout.
SWITCH_MARGIN = 32


def v_bg(raw, paste_dy, camy):
    """Sonic 2's BG row at the screen top for ACT camera Y `camy` (the zone pasted at dy)."""
    return ((camy - paste_dy) >> raw["v_factor"]) + raw["v_offset"]


def _tall_source(donor, zone, donor_cam_x_max, v_hi):
    """(raw, kind_of) for a tall-capable zone. kind_of(bg_row) is Sonic 2's kind for that row,
    read DIRECTLY from the table: both writers index their table from the screen top's row
    through a mask and then walk it forward, so row r's kind is table[r] for every screen top
    below the mask's period, which is refused otherwise (Hidden Palace's 1024-row index wrap,
    Wing Fortress's $7FF row mask)."""
    with open(s2_asm_path(donor), errors="replace") as fh:
        text = fh.read()
    raw = TALL_RAW[zone](text)
    if zone == "WFZ":
        if donor_cam_x_max >= raw["transition_x"]:
            raise ClipScrollError(
                f"WFZ: a clip camera reaches donor X {donor_cam_x_max}, past SwScrl_WFZ's "
                f"transition at ${raw['transition_x']:X}, where the Transition array scrolls "
                f"rows 1408..1791 differently; one band chain cannot be both")
        table, period = raw["arrays"]["Normal"], raw["row_mask"] + 1
    else:
        table, period = raw["kinds"], raw["wrap"]
    if v_hi >= period:
        raise ClipScrollError(f"{zone}: a screen top reaches BG row {v_hi}, past the "
                              f"{period}-row period its scroll table is indexed through")
    return raw, table.get


def tall_extent(donor, zone, paste_dy, cam_lo, cam_hi, map_lines):
    """The tall map a clip zone needs, or None when its plane window already holds every
    screen top its clips reach (then nothing changes: the zone keeps the windowed path).

    `cam_lo`/`cam_hi` are the act camera tops (Y) its clips can hold (dst.y .. dst.y + h - 224);
    `map_lines` is the donor background's height. Returns {"r0" (first BG row, a chunk row),
    "rows" (tile rows), "v_lo", "v_hi" (screen-top BG rows reached)}. The map runs from the
    chunk row holding the highest top to the chunk row holding the lowest screen's last line,
    capped at the donor map (where the engine's own clamp then holds, as Sonic 2's map ends)."""
    import clip_bg_lower
    if zone not in TALL_RAW or DERIVER_DONOR.get(zone) != donor:
        return None
    with open(s2_asm_path(donor), errors="replace") as fh:
        raw = TALL_RAW[zone](fh.read())
    v_lo, v_hi = (max(0, v_bg(raw, paste_dy, c)) for c in (cam_lo, cam_hi))
    r0 = clip_bg_lower.window_top(donor, zone)
    if r0 <= v_lo and v_hi <= r0 + PLANE_CEILING:
        return None
    top = v_lo // CHUNK_LINES * CHUNK_LINES
    end = min(map_lines, -(-(v_hi + SCREEN_LINES) // CHUNK_LINES) * CHUNK_LINES)
    if end - top < TALL_MIN_SPAN:
        raise ClipScrollError(f"{zone}: screen tops {v_lo}..{v_hi} leave window {r0} yet fit "
                              f"{end - top} lines, which is not a tall map; a different "
                              f"window rule is wanted, not this path")
    return {"r0": top, "rows": (end - top) // 8, "v_lo": v_lo, "v_hi": v_hi}


def _runs(ok, lo):
    """[(start, end)] inclusive runs of True in `ok`, indexed from `lo`."""
    out, s = [], None
    for i, v in enumerate(list(ok) + [False]):
        if v and s is None:
            s = i
        elif not v and s is not None:
            out.append((lo + s, lo + i - 1))
            s = None
    return out


def derive_tall(donor, zone, paste_dy, ext, words, donor_cam_x_max):
    """The band chain for one tall zone: {"specs": [spec per window config, top to bottom],
    "switch_rows": [BG screen-top row where config i hands to i + 1], "overlap": [(a, b)]
    (the screen tops where both are exact), "cuts": [act camera-CENTRE Y of each switch]}.

    `words` are the tall map's lowered cells (clip_bg_lower.lower(rows=ext["rows"])): a tile
    row whose 64 cells are all transparent can show no hscroll, so its kind is free."""
    r0, n = ext["r0"], ext["rows"] * 8
    raw, kind_of = _tall_source(donor, zone, donor_cam_x_max, ext["v_hi"])
    cols = len(words) // ext["rows"]
    wild = {r0 + 8 * t + i for t in range(ext["rows"])
            if not any(words[t * cols:(t + 1) * cols]) for i in range(8)}

    def K(r):
        return None if r in wild or not r0 <= r < r0 + n else kind_of(r)

    lo = max(ext["v_lo"], r0)
    hi = min(ext["v_hi"], r0 + n - SCREEN_LINES)
    lines = range(lo, hi + SCREEN_LINES)
    cands = {}
    for a in range(0, n, 8):
        C = []
        for p in range(PLANE_LINES):
            k = K(r0 + a + ((p - a) % PLANE_LINES))
            if k is None:                   # free here: take any alias that is not
                k = next((K(r0 + m) for m in range(p, n, PLANE_LINES)
                          if K(r0 + m) is not None), None)
            C.append(k)
        first = next((k for k in C if k is not None), None)
        if first is None:
            raise ClipScrollError(f"{zone}: the tall map has no painted row")
        for p in range(PLANE_LINES):        # a free line joins the band above it
            if C[p] is None:
                C[p] = C[p - 1] if p else first
        cands.setdefault(tuple(C), a)
    runs = []
    for C in cands:
        pre = [0]
        for r in lines:
            k = K(r)
            pre.append(pre[-1] + (k is not None and C[(r - r0) % PLANE_LINES] != k))
        ok = [pre[v - lo + SCREEN_LINES] == pre[v - lo] for v in range(lo, hi + 1)]
        runs += [(s, e, C) for s, e in _runs(ok, lo)]
    pool = [r for r in runs if r[0] <= lo <= r[1]]
    if not pool:
        raise ClipScrollError(f"{zone}: no band layout is exact for screen top {lo}")
    chain = [max(pool, key=lambda r: r[1])]
    while chain[-1][1] < hi:
        cur = chain[-1]
        pool = [r for r in runs if cur[0] < r[0] <= cur[1] < r[1]]
        if not pool:
            raise ClipScrollError(f"{zone}: no band layout is exact past screen top "
                                  f"{cur[1]} while overlapping the one that ends there")
        # PREFER an overlap of SWITCH_MARGIN rows (the switch sits in its middle), so a
        # scroll that trails its camera (Step 5's rate clamp) still meets an exact layout;
        # take the widest overlap there is when no neighbour offers that much.
        wide = [r for r in pool if cur[1] - r[0] >= SWITCH_MARGIN] or \
            [max(pool, key=lambda r: (cur[1] - r[0], r[1]))]
        chain.append(max(wide, key=lambda r: (r[1], -r[0])))
    specs, switch, overlap, cuts = [], [], [], []
    for i, (s, e, C) in enumerate(chain):
        kinds = {r0 + p: C[p] for p in range(PLANE_LINES)}
        bands, v_off, approx = _finish_plane(kinds, raw["v_factor"], raw["v_offset"], r0, r0,
                                             f"{zone} tall config {i}")
        spec = {"zone": zone, "routine": raw["routine"], "v_factor": raw["v_factor"],
                "v_center": paste_dy, "v_offset": v_off, "bands": bands, "window_top": r0,
                "approximations": approx, "provenance": raw["provenance"], "bg_span": n,
                "tall": {"index": i, "of": len(chain), "valid": (max(s, lo), min(e, hi))}}
        if len(chain) > 1:
            spec["transition"] = 1          # a lerp between two band layouts is neither
        specs.append(_nonneg_center(spec))
        if i:
            a, b = chain[i][0], chain[i - 1][1]
            v = (a + b) // 2
            overlap.append((a, b))
            switch.append(v)
            cuts.append(((v - raw["v_offset"]) << raw["v_factor"]) + paste_dy + CAM_HALF_H)
    if len(specs) > 1:
        for k in range(max(len(sp["bands"]) for sp in specs)):
            rates = {(sp["bands"][k].get("drift") or 0) if k < len(sp["bands"]) else 0
                     for sp in specs}
            if len(rates) > 1:
                raise ClipScrollError(
                    f"{zone}: band {k} drifts at {sorted(rates)} across the chain's configs; "
                    f"Parallax_Drift_Acc is kept per band INDEX across a config switch, so the "
                    f"clouds would jump")
    return {"specs": specs, "switch_rows": switch, "overlap": overlap, "cuts": cuts,
            "r0": r0, "rows": ext["rows"], "span": n, "v_lo": lo, "v_hi": hi}


def vertical_coverage(donor, zone, paste_dy, cams, pick, wild=frozenset(),
                      donor_cam_x_max=0):
    """(exact, total, first_miss) over the act camera tops `cams`: a camera top is EXACT when
    the engine's screen-top BG row (engine_vscroll + the spec's window_top, clamps included)
    is Sonic 2's (v_bg), and every visible line whose BG row is not transparent (`wild`)
    takes Sonic 2's kind for that row (the band the engine selects by PLANE line, compared as
    Sonic 2's own ratio, `s2_ratio` where the engine approximates it, or drift rate).
    `pick(camy)` is the spec the engine uses at that camera (a tall chain's layout, or the
    zone's one windowed spec). The measure WINDOWED-BG-VERTICAL-CLAMP was booked on."""
    raw, kind_of = _tall_source(donor, zone, donor_cam_x_max, 0)
    exact, first = 0, None
    for camy in cams:
        spec = pick(camy)
        vs = engine_vscroll(spec, camy)
        top = vs + spec["window_top"]
        ok = top == v_bg(raw, paste_dy, camy)
        tops = [b["plane_top"] for b in spec["bands"]]
        for line in range(SCREEN_LINES) if ok else ():
            r = top + line
            if r in wild:
                continue
            b = spec["bands"][max(i for i, t in enumerate(tops) if t <= (vs + line) % PLANE_LINES)]
            got = ("drift", b["drift"]) if b.get("drift") else ("flat", b.get("s2_ratio", b["ratio"]))
            if got != kind_of(r):
                ok = False
                break
        exact += ok
        if not ok and first is None:
            first = camy
    return exact, len(cams), first


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
        if b.get("drift"):
            args.append(f"drift: SceneDrift.Rate({b['drift']})")
        rows.append("layer(" + ", ".join(args) + ")")
    rows += ["no_layer()"] * (MAX_BANDS - len(rows))
    table_label = spec.get("table_label", table_label)
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
    tables = {}
    for _k, spec in zones:
        if uses_ripple(spec):
            lab = spec.get("table_label", TABLE_LABEL)
            tab = tuple(spec["deform_table"])
            if tables.setdefault(lab, tab) != tab:
                raise ClipScrollError(f"two zones derive DIFFERENT ripple tables under one label "
                                      f"{lab}; this block emits one per label")
    for lab in sorted(tables, key=lambda x: (x != TABLE_LABEL, x)):
        tab = list(tables[lab])
        body = ",\n    ".join(", ".join(str(v) for v in tab[i:i + 32]) for i in range(0, 256, 32))
        rev = ("" if lab == TABLE_LABEL else
               "// REVERSED (entry k is the cycle's entry -k): Sonic 2 writes this zone's ripple\n"
               "// rows bottom up, so its index falls down the screen (clip_bg_scroll derive_ooz).\n")
        out.append(
            "// SwScrl_RippleData's cycle, repeated to the engine's 256-entry deform table. SPEED 0\n"
            "// (static): S2 advances it one entry per 8 frames and the engine's phase moves in\n"
            "// whole entries per frame (booked engine gap).\n" + rev +
            f"pub data {lab}: [i8; 256] = [\n    {body}\n]\n")
    names = []
    for key, spec in zones:
        lab = SCENE_LABEL.format(key=key)
        names.append(lab)
        prov = ", ".join(f"{k} s2.asm line {v}" for k, v in spec["provenance"].items())
        rows = "\n".join(
            f"//   plane line {top:>3}{'' if end is None else f'..{end - 1:<3}'}  {what}"
            for top, end, what, _f, _src in band_rows(spec))
        out.append(f"// zone key {key}: {spec['zone']} ({spec['routine']}; {prov})\n{rows}\n")
        # a tall zone's CHAIN of band layouts switches instantly whatever the act says
        # (derive_tall: a lerp between two layouts is neither); every other spec takes the act's
        out.append(scene_text(spec, lab, TABLE_LABEL, spec.get("transition", transition)))
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
        if b.get("drift"):
            what += f" + drift {b['drift']}/256 px/frame"
        if "s2_ratio" in b:
            what += f" (APPROXIMATES Sonic 2's camX*{b['s2_ratio']})"
        out.append((b["plane_top"], b.get("engine_end"), what, b["factor"],
                    b.get("loops") or b.get("src")))
    return out


# ---------------------------------------------------------------------------
# the engine model and the comparison (what the parcel measures)
# ---------------------------------------------------------------------------

def engine_vscroll(spec, camy, ceiling=None):
    """Parallax_Step5_Vscroll at steady state: the BG vertical scroll, clamped to
    [0, ceiling]: VSCROLL_BG_MAX when the region authors no rg_bg_span, `span - 224` on a
    TALL map's rows (the spec carries its `bg_span`, which the bake writes as rg_bg_span)."""
    if ceiling is None:
        ceiling = (spec["bg_span"] - SCREEN_LINES) if spec.get("bg_span") else PLANE_CEILING
    if spec["v_factor"] == LOCKED:
        v = spec["v_offset"]
    else:
        v = (_sx(camy - spec["v_center"], 16) >> spec["v_factor"]) + spec["v_offset"]
    return min(max(v, 0), ceiling)


def engine_bg_words(spec, camx, table=None, vscroll=None, phase_bg=0, drift_px=None):
    """The BG HScroll word the engine's fill writes on each screen line at steady state
    (Parallax_Fill_PerLine's flat, sampled and curve loops). `vscroll` is the BG plane's
    vertical scroll (a locked scene's v_offset when None); `phase_bg` is
    Parallax_Deform_Phase_BG. Bands are keyed by PLANE line: a screen line L shows plane row
    (vscroll + L) mod 512 and takes the band whose top is the last at or above that row. A
    curve is modelled only on a locked plane (the one place this parcel authors one).

    `drift_px` is Parallax_Drift_Acc's PIXEL word per CONFIG BAND INDEX (scene_text emits one
    layer per spec band, in order, so config band k is spec band k). Parallax_Update adds it
    to every band's plane-B target (`add.w (a4), d2`, CAP_BAND_DRIFT), so it is added here to
    every band; only a band with a drift rate ever has a non-zero accumulator. None = all 0."""
    bands = spec["bands"]
    dpx = list(drift_px or []) + [0] * (len(bands) - len(drift_px or []))
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
            k = [i for i, x in enumerate(bands) if x["plane_top"] <= row][-1]
            b = bands[k]
            v = -engine_factor_scroll(b["factor"], camx) + dpx[k]
            if b["kind"] == "ripple":
                v += tab[(phase_bg + b["phase"] + vscroll + line) & 0xFF]
            out[line] = _sx(v, 16)
        return out
    for k, b in enumerate(bands):
        top = b["plane_top"]
        end = bands[k + 1]["plane_top"] if k + 1 < len(bands) else SCREEN_LINES
        base = _sx(-engine_factor_scroll(b["factor"], camx) + dpx[k], 16)
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
