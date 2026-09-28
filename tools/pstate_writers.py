#!/usr/bin/env python3
"""pstate_writers.py — every path in the BUILT ROM that installs a player_state, and the
state each one installs, DERIVED rather than enumerated by hand.

WHY THIS EXISTS (GPP-INSTASHIELD-WALKOFF, docs/DEFERRED_WORK.md; audit row in
docs/research/2026-09-26-gate-predicate-audit.md). instashield_gate.py proves each
ability hook refuses every player_state except the two from-a-jump states. The PROMISE
is narrower and different: "a jump press made after walking off a ledge must NOT fire
the ability". The step between them — "a walk-off never installs a from-a-jump state" —
rested on a one-time hand enumeration of state writers, and the audit measured the hole:
`Ground_DetachState`'s `moveq #PSTATE_AIR` mutated to `#PSTATE_JUMP` left the gate at
exit 0. This module closes that step on every build.

WHAT IT DERIVES, and from where:

  1. THE SITES, from the ROM. Player_SetState is the one transition writer of
     player_state (its own header). Every 68000 transfer encoding that can reach it —
     bsr/bra/Bcc in both displacement widths, jsr/jmp abs.w/abs.l/d16(pc) — is searched
     for over the WHOLE ROM image, so a caller the source scan below missed cannot hide.
     Each hit is attributed to the routine (listing symbol) that contains it.

  2. THE SAME SITES, from the source. Every `.emp` file the build's own Source Digest
     says it READ is scanned for references to Player_SetState. A transfer names its
     enclosing proc; ANY OTHER reference (an address taken, a table entry) is a path this
     module cannot follow and is refused loudly. The two derivations must agree
     routine-for-routine: a ROM routine the source does not name, or a built source proc
     with no ROM site, is a failure, not a note.

  3. THE STATE EACH SITE INSTALLS, by a d0 dataflow over the routine's decoded bytes
     (capstone, decoded along control flow from the routine's entry). d0 at a site is a
     set of constants or UNKNOWN; a callee's effect on d0 is itself derived by analysing
     the callee (bounded depth), and a `movem.l d0,-(sp)` / `movem.l (sp)+,d0` pair
     restores the saved value. A site whose d0 is UNKNOWN, or a scanned site the flow
     never reaches, is UNMEASURABLE and fails loudly by name.

  4. DIRECT WRITES of the state byte that bypass Player_SetState, from the source: every
     instruction whose DESTINATION names player_state / _pl_state / PL_STATE_OFF. Only
     `clr.b` (value 0), `move.b #CONST` (resolved through the build's equates) and
     Player_SetState's own `move.b d0` are understood; anything else is refused loudly.

The caller (instashield_gate.py, pass_walkoff) then judges each installed value by
EXECUTING the ability routines on it — never by comparing against a literal copy of
{PSTATE_JUMP, PSTATE_ROLLJUMP}.

WHAT IS NOT SEEN, stated rather than hidden: a write of the state byte through a raw
numeric displacement (`$32(a0)`) or through a comptime macro body that takes the field
as a parameter. Neither form exists in the tree today; the ROM-wide transfer scan does
not depend on the source and so is not blinded by either.
"""

import pathlib
import re

import capstone

TOP = "TOP"          # d0 unknown
ENTRY = "ENTRY"      # d0 as it was on entry (used only while analysing a callee)
MAX_CALL_DEPTH = 3

_MD = None


def _md():
    global _MD
    if _MD is None:
        _MD = capstone.Cs(capstone.CS_ARCH_M68K,
                          capstone.CS_MODE_BIG_ENDIAN | capstone.CS_MODE_M68K_000)
    return _MD


class Unmeasurable(Exception):
    """This module could not derive what it was asked about. Never a pass."""


# --------------------------------------------------------------------------
# 1. ROM-wide transfer scan
# --------------------------------------------------------------------------

def _w(rom, o):
    return (rom[o] << 8) | rom[o + 1]


def _sext16(v):
    return v - 0x10000 if v & 0x8000 else v


def _sext8(v):
    return v - 0x100 if v & 0x80 else v


def scan_transfers(rom, target):
    """[(addr, form)] — every even offset whose bytes ENCODE a transfer to `target`.

    Searched over the whole image, instruction boundaries unknown, so a hit can in
    principle be an operand word of another instruction or a data word; the caller
    requires every hit to be an instruction the dataflow actually reaches, which turns
    such a coincidence into a loud UNMEASURABLE rather than a silent extra site."""
    hits = []
    n = len(rom)
    for o in range(0, n - 1, 2):
        w = _w(rom, o)
        if (w & 0xF000) == 0x6000:
            cond = (w >> 8) & 0xF
            d8 = w & 0xFF
            if d8 == 0:
                if o + 4 > n:
                    continue
                tgt = o + 2 + _sext16(_w(rom, o + 2))
                width = "w"
            elif d8 == 0xFF:
                continue                  # 68020+ 32-bit displacement; not a 68000 form
            else:
                tgt = o + 2 + _sext8(d8)
                width = "s"
            if tgt == target:
                kind = {0: "bra", 1: "bsr"}.get(cond, "bcc")
                hits.append((o, "%s.%s" % (kind, width)))
        elif w in (0x4EB9, 0x4EF9) and o + 6 <= n:
            if ((_w(rom, o + 2) << 16) | _w(rom, o + 4)) == target:
                hits.append((o, "jsr.l" if w == 0x4EB9 else "jmp.l"))
        elif w in (0x4EB8, 0x4EF8) and o + 4 <= n:
            if (_sext16(_w(rom, o + 2)) & 0xFFFFFF) == target:
                hits.append((o, "jsr.w" if w == 0x4EB8 else "jmp.w"))
        elif w in (0x4EBA, 0x4EFA) and o + 4 <= n:
            if o + 2 + _sext16(_w(rom, o + 2)) == target:
                hits.append((o, "jsr.pc" if w == 0x4EBA else "jmp.pc"))
    return hits


# --------------------------------------------------------------------------
# Routine extents from the listing
# --------------------------------------------------------------------------

def is_local(name):
    return name.startswith("$")


class Extents:
    """Routine heads and extents from the listing's symbol block. A routine's own
    hygienic local labels (`$module$Routine$label`) are not boundaries; neither is a
    PHASED symbol (its listing value is a bank-local VMA — see instashield_gate's note
    above routine_extent)."""

    def __init__(self, syms, phased):
        self.syms = syms
        self.phased = set(phased)
        rows = sorted((a, n) for n, a in syms.items() if n not in self.phased)
        self.rows = rows
        self.addrs = [a for a, _ in rows]

    def head_at_or_below(self, addr):
        import bisect
        i = bisect.bisect_right(self.addrs, addr) - 1
        while i >= 0:
            a, n = self.rows[i]
            if not is_local(n):
                return n, a
            i -= 1
        return None, None

    def extent(self, name):
        start = self.syms.get(name)
        if start is None or name in self.phased:
            return None
        # EVERY `$`-prefixed symbol is a hygienic local (`$module$scope$label`, three
        # parts, measured: all 2053 in s4.debug.lst on 2026-09-28) — the routine's own
        # AND the ones a macro expansion inside it mints (`$...$asm6$abs` from abs_w).
        # instashield_gate.routine_extent excludes only the routine's own prefix, which
        # is right for its two subjects (no macro locals) and wrong in general: it cut
        # Air_Collide at its first abs_w expansion, 0xC4 bytes short.
        above = [a for a, n in self.rows if a > start and not is_local(n)]
        if not above:
            return None
        return start, min(above)

    def name_at(self, addr):
        for a, n in self.rows:
            if a == addr and not is_local(n):
                return n
        return None


# --------------------------------------------------------------------------
# 3. The d0 dataflow
# --------------------------------------------------------------------------

_RLIST = re.compile(r"^[ad][0-7](-[ad][0-7])?(/[ad][0-7](-[ad][0-7])?)*$")
_IMM = re.compile(r"^#(-)?\$?([0-9a-fA-F]+)$")
_ABS = re.compile(r"^\$([0-9a-fA-F]+)(\.[wl])?$")
_PCREL = re.compile(r"^\$([0-9a-fA-F]+)\(pc\)$")

READ_ONLY = {"tst", "cmp", "cmpi", "cmpa", "cmpm", "btst", "chk", "nop", "illegal",
             "trap", "trapv", "stop", "reset", "pea", "link", "unlk"}
TERMINATORS = {"rts", "rte", "rtr"}
BCC = {"bhi", "bls", "bcc", "bhs", "bcs", "blo", "bne", "beq", "bvc", "bvs", "bpl",
       "bmi", "bge", "blt", "bgt", "ble"}


def _split_ops(op_str):
    out, depth, cur = [], 0, ""
    for ch in op_str:
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


def reg_set(tok):
    """The registers a PURE register / register-list operand names; empty for memory."""
    tok = tok.replace("sp", "a7")
    if not _RLIST.match(tok):
        return frozenset()
    out = set()
    for part in tok.split("/"):
        if "-" in part:
            a, b = part.split("-")
            if a[0] != b[0]:
                return frozenset({"?"})
            for i in range(int(a[1]), int(b[1]) + 1):
                out.add("%s%d" % (a[0], i))
        else:
            out.add(part)
    return frozenset(out)


def _target(tok):
    """An absolute transfer target from a capstone operand, or None (indirect)."""
    m = _ABS.match(tok)
    if m:
        v = int(m.group(1), 16)
        if m.group(2) == ".w" and v & 0x8000:
            v = (v - 0x10000) & 0xFFFFFF
        return v
    m = _PCREL.match(tok)
    if m:
        return int(m.group(1), 16)
    return None


def _imm(tok):
    m = _IMM.match(tok)
    if not m:
        return None
    v = int(m.group(2), 16)
    return -v if m.group(1) else v


def _join_val(a, b):
    if a == TOP or b == TOP:
        return TOP
    return a | b


def _join_stack(a, b):
    return a if a == b else None


def decode_one(rom, pc):
    if pc < 0 or pc + 2 > len(rom):
        return None
    for insn in _md().disasm(rom[pc:pc + 10], pc, 1):
        return insn
    return None


class Flow:
    """d0 dataflow over routines of one ROM. Memoises callee summaries."""

    def __init__(self, rom, extents, target, noreturn=()):
        self.rom = rom
        self.ext = extents
        self.target = target
        # Addresses of procs the SOURCE marks `@noreturn` (source_noreturn). A call to
        # one ends the path: the `assert` macro's failure arm is `jsr ErrorHandlerBlob`
        # followed by its message string, and following it decodes text as code. This
        # can never hide a SITE (every scanned site must still be reached, or it fails
        # loudly); it can only drop values from a path that genuinely stops there.
        self.noreturn = frozenset(noreturn)
        self._summ = {}

    # ---- callee summary: the d0 values at every return, over an ENTRY d0 ----
    def summary(self, addr, depth):
        if addr == self.target:
            return TOP          # its enter hook is an indirect jmp; nothing to derive
        if addr in self._summ:
            s = self._summ[addr]
            return TOP if s is None else s       # None = in progress (recursion)
        if depth > MAX_CALL_DEPTH:
            return TOP
        name = self.ext.name_at(addr)
        ex = self.ext.extent(name) if name else None
        if ex is None:
            return TOP
        self._summ[addr] = None
        try:
            res = self.analyse(ex[0], ex[1], frozenset({ENTRY}), depth + 1)
            rets = res["rets"]
        except Unmeasurable:
            rets = TOP
        self._summ[addr] = rets
        return rets

    def analyse(self, start, end, entry_val=TOP, depth=0):
        """Worklist over the routine's control flow from `start`. Returns
        {sites: {addr: valueset|TOP}, rets: valueset|TOP, visited: set, notes: [...]}.
        A value set may contain ENTRY while summarising a callee."""
        states = {start: (entry_val, ())}
        work = [start]
        sites, rets, visited, notes = {}, frozenset(), set(), []

        def merge(pc, val, stack):
            if pc in states:
                ov, os_ = states[pc]
                nv, ns = _join_val(ov, val), _join_stack(os_, stack)
                if (nv, ns) == (ov, os_):
                    return
                states[pc] = (nv, ns)
            else:
                states[pc] = (val, stack)
            work.append(pc)

        def site(pc, val):
            sites[pc] = _join_val(sites.get(pc, frozenset()), val)

        steps = 0
        while work:
            steps += 1
            if steps > 20000:
                raise Unmeasurable("dataflow did not converge in $%06X..$%06X"
                                   % (start, end))
            pc = work.pop()
            val, stack = states[pc]
            if not (start <= pc < end):
                raise Unmeasurable("flow left $%06X..$%06X at $%06X"
                                   % (start, end, pc))
            insn = decode_one(self.rom, pc)
            if insn is None:
                raise Unmeasurable("capstone cannot decode $%06X (inside $%06X..$%06X)"
                                   % (pc, start, end))
            visited.add(pc)
            nxt = pc + insn.size
            mn = insn.mnemonic
            base = mn.split(".")[0]
            size = mn.split(".")[1] if "." in mn else None
            ops = _split_ops(insn.op_str) if insn.op_str else []

            def fall(v=val, s=stack):
                if nxt >= end:
                    notes.append("falls through its end at $%06X into the next routine"
                                 % nxt)
                    return
                merge(nxt, v, s)

            if base in TERMINATORS:
                rets = _join_val(rets, val)
                continue
            if base in ("bra", "jmp") or base in BCC:
                tgt = _target(ops[0]) if ops else None
                if tgt == self.target:
                    site(pc, val)
                elif tgt is not None and start <= tgt < end:
                    merge(tgt, val, stack)
                elif tgt is None and base == "jmp":
                    notes.append("indirect jmp at $%06X (%s) — not followed"
                                 % (pc, insn.op_str))
                if base in BCC:
                    fall()
                continue
            if base.startswith("db"):             # dbcc Dn, target
                w = reg_set(ops[0])
                v = TOP if "d0" in w else val
                tgt = _target(ops[1])
                if tgt is not None and start <= tgt < end:
                    merge(tgt, v, stack)
                fall(v)
                continue
            if base in ("bsr", "jsr"):
                tgt = _target(ops[0]) if ops else None
                if tgt == self.target:
                    site(pc, val)
                if tgt is None:
                    fall(TOP)
                    continue
                if tgt in self.noreturn:
                    continue
                summ = self.summary(tgt, depth)
                if summ == TOP:
                    v = TOP
                elif ENTRY in summ:
                    v = _join_val(summ - {ENTRY}, val)
                else:
                    v = summ
                fall(v)
                continue

            # ---- straight-line instructions: d0 and the modelled stack ----
            v, s = val, stack
            if base == "movem" and len(ops) == 2:
                src_regs, dst_regs = reg_set(ops[0]), reg_set(ops[1])
                if src_regs and ops[1] in ("-(a7)", "-(sp)"):
                    s = None if s is None else s + ((src_regs,
                                                     val if "d0" in src_regs else None),)
                elif dst_regs and ops[0] in ("(a7)+", "(sp)+"):
                    if s:
                        regs, saved = s[-1]
                        s = s[:-1]
                        if "d0" in dst_regs:
                            v = saved if regs == dst_regs else TOP
                    else:
                        s = None
                        if "d0" in dst_regs:
                            v = TOP
                elif dst_regs:
                    if "d0" in dst_regs:
                        v = TOP
                    if "a7" in dst_regs:
                        s = None
                fall(v, s)
                continue
            if base == "move" and len(ops) == 2 and ops[1] in ("-(a7)", "-(sp)"):
                s = None if s is None else s + ((frozenset({ops[0]}) if ops[0] == "d0"
                                                 else frozenset(),
                                                 val if ops[0] == "d0" else None),)
                fall(v, s)
                continue
            if base == "move" and len(ops) == 2 and ops[0] in ("(a7)+", "(sp)+"):
                if s:
                    regs, saved = s[-1]
                    s = s[:-1]
                else:
                    regs, saved, s = frozenset(), None, None
                if ops[1] == "d0":
                    v = saved if (regs == frozenset({"d0"}) and size == "l") else TOP
                fall(v, s)
                continue
            if base == "exg":
                if any("d0" in reg_set(o) for o in ops):
                    v = TOP
                if any("a7" in reg_set(o) for o in ops):
                    s = None
                fall(v, s)
                continue
            if base in READ_ONLY or not ops:
                fall(v, s)
                continue
            written = reg_set(ops[-1])
            if "?" in written:
                v, s = TOP, None
            if "a7" in written:
                s = None
            if "d0" in written:
                imm = _imm(ops[0]) if len(ops) == 2 else None
                if base == "moveq" and imm is not None:
                    v = frozenset({imm & 0xFF})
                elif base == "move" and imm is not None:
                    v = frozenset({imm & 0xFF})
                else:
                    v = TOP
            fall(v, s)

        return {"sites": sites, "rets": rets, "visited": visited, "notes": notes}


# --------------------------------------------------------------------------
# 2 + 4. Source derivation
# --------------------------------------------------------------------------

_PROC = re.compile(r"^\s*(?:pub\s+)?proc\s+([A-Za-z_]\w*)")
_MODULE = re.compile(r"^\s*module\s+([\w.]+)")
_XFER = re.compile(r"^\s*(?:\.?[\w$]+:\s*)?(j?bsr|j?bra|jsr|jmp|b(?:hi|ls|cc|hs|cs|lo|ne|eq|"
                   r"vc|vs|pl|mi|ge|lt|gt|le))(?:\.[swl])?\s+%s\b")
_INSN = re.compile(r"^\s*(?:\.?[\w$]+:\s*)?([a-z]{2,7})(?:\.([bwls]))?\s+(.+)$")
_NOT_INSNS = {"use", "pub", "equ", "const", "ensure", "return", "fn", "let", "if",
              "for", "vars", "struct", "module", "proc", "comptime", "else", "while",
              "section", "offsets", "assert", "in"}
STATE_FIELDS = ("player_state", "_pl_state", "PL_STATE_OFF")


def digest_sources(lst_path, root):
    """The `.emp` files the build's own Source Digest records it READ (origin=source)."""
    out = []
    for line in pathlib.Path(lst_path).read_text(errors="replace").splitlines():
        if not line.startswith("DIGEST-READ "):
            continue
        f = dict(kv.split("=", 1) for kv in line.split()[1:] if "=" in kv)
        if f.get("origin") == "source" and f.get("path", "").endswith(".emp"):
            out.append(pathlib.Path(root) / f["path"])
    return out


def source_noreturn(paths):
    """Names of procs declared under an `@noreturn` attribute in the given sources."""
    out = set()
    for p in paths:
        pending = False
        for raw in p.read_text(errors="replace").splitlines():
            s = _code(raw).strip()
            if not s:
                continue
            if s.startswith("@noreturn"):
                pending = True
                continue
            if pending:
                m = _PROC.match(s)
                if m:
                    out.add(m.group(1))
                pending = s.startswith("@")      # further attributes may stack
    return out


def _code(line):
    return line.split("//", 1)[0]


def source_scan(paths, callee="Player_SetState"):
    """({proc: [(file, line)]} transfer sites, [refused references], [direct writes]).

    direct writes are (file, line, proc, mnemonic, size, src_operand)."""
    xfer = re.compile(_XFER.pattern % re.escape(callee))
    sites, refused, writes = {}, [], []
    for p in paths:
        text = p.read_text(errors="replace").splitlines()
        proc, in_use = None, False
        for i, raw in enumerate(text, 1):
            code = _code(raw)
            m = _PROC.match(code)
            if m:
                proc = m.group(1)
            s = code.strip()
            if s.startswith("use "):
                in_use = "}" not in s and "{" in s
                continue
            if in_use:
                if "}" in s:
                    in_use = False
                continue
            if re.search(r"\b%s\b" % re.escape(callee), code):
                if m and m.group(1) == callee:
                    pass
                elif xfer.match(code):
                    sites.setdefault(proc, []).append((str(p), i))
                else:
                    refused.append("%s:%d: `%s` — a reference to %s that is not a "
                                   "direct transfer; this module cannot follow it"
                                   % (p, i, s, callee))
            if any(re.search(r"\b%s\b" % f, code) for f in STATE_FIELDS):
                mi = _INSN.match(code)
                if not mi or mi.group(1) in _NOT_INSNS:
                    continue
                ops = _split_ops(mi.group(3).strip())
                if not ops or not any(re.search(r"\b%s\b" % f, ops[-1])
                                      for f in STATE_FIELDS):
                    continue                  # the field is only READ here
                if mi.group(1) in READ_ONLY:
                    continue
                writes.append((str(p), i, proc, mi.group(1), mi.group(2),
                               ops[0] if len(ops) > 1 else None))
    return sites, refused, writes
