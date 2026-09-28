#!/usr/bin/env python3
"""layer_sensor_arm.py — the collision half of layer_line_gate's promise: every collision
sensor in the BUILT ROM selects its plane from the player's layer byte.

WHY THIS EXISTS (GPP-CROSSOVER-SENSORS, docs/DEFERRED_WORK.md; audit row in
docs/research/2026-09-26-gate-predicate-audit.md). layer_line_gate executes
Player_LayerLines and proves the lines DECIDE `Sst.layer`. The promise a layer line makes
is that crossing it changes which collision plane the player stands on, and that half was
checked by nothing: `Player_SensorSurface`'s `move.b layer(a0), d3` -> `nop` built green
through every lane of `DEBUG=1 ./build.sh` (re-measured 2026-09-28 on 19b960d4, after the
painted-marks gate the audit named was retired). This module is the missing arm; layer_line_gate
runs it, so build.sh's existing `layer_line_gate.py` call gates it.

THE SUBJECT IS THE PLANE SELECTOR'S CALLERS, NOT THE LAYER READS. Starting from the reads
would have been blind to exactly the audited mutation: a read that is deleted is not in a
read set. So the arm starts at the one routine that turns d3.b into a plane
(`Collision_GetType`, `tst.b d3` -> +TILE_CACHE_COLL_SIZE; its header states the register
convention every sensor entry must follow) and walks OUTWARD over the ROM:

  A. STATIC, ROM-wide (every sensor path, including the ones inside big state routines
     that cannot be executed in isolation: PState_Climb, Glide_Collide, ...).
     Every transfer that can reach a member of the plane-carrying family F is searched for
     over the whole ROM image (pstate_writers.scan_transfers: bsr/bra/Bcc/jsr/jmp in every
     encoding) plus every address REFERENCE to a member (lea/pea, pc-relative or absolute —
     Player_SensorSurface hands a probe core to Player_SensorPair in a2). Each containing
     routine is analysed along its control flow from its entry with d3.b = ENTRY, and the
     d3.b value at each such transfer is one of:
        LAYER   the byte `move.b <SST_layer>(a0), d3` loaded on this path  -> a HANDOFF, graded
        ENTRY   the routine's own incoming d3 (possibly via stack save/peek/restore) -> the
                routine is itself a CARRIER: it joins F and ITS callers are searched in turn
        other   a constant, anything computed, anything unknown        -> FAIL (exit 1)
     `jsr (aN)` with aN = the routine's incoming aN makes it a carrier ON aN (Player_SensorPair);
     a call to such a routine while aN holds an F member's address is graded the same way.
     Jump tables (`move.w T(pc,dN.w),dN / jmp T(pc,dN.w)`) are resolved from the ROM; a
     transfer this pass cannot resolve, a scanned hit the flow never reaches, a stack it
     cannot follow, or an EMPTY handoff set is UNMEASURABLE (exit 2), never a pass.

  B. EXECUTED (every handoff routine whose calls all stay inside F, i.e. the sensor entries
     themselves, and through them every carrier down to Collision_GetType's own plane
     select). Each is run from its entry, with a synthetic SST whose layer byte is 0 and then
     1, over a synthetic tile cache whose two planes hold the same attribute (air, a full
     block, a partial one — taken from this ROM's own SolidityTable/HeightMaps), every
     quadrant, direction and policy seed. EVERY byte read from Tile_Cache_Collision must lie
     in the plane the layer byte names, at least one must happen per run, and every call
     instruction inside every carrier must have executed under BOTH layers (so a probe core's
     forward/back re-probe, which reloads the layer off the stack, is exercised rather than
     assumed).

THE DERIVED LAYER-READ SET is the set of reads that produced a LAYER value at a graded
handoff. It is cross-checked against the Source Digest's `.emp` files: every source
instruction that loads `layer(...)` into a register must sit in a proc the ROM analysis
graded, with the same count per proc (exit 2 otherwise). Flag-only reads (`tst.b layer(a0)`
in Player_DebugExit, a priority derivation) are listed, not graded: they select no plane.

WHAT IS NOT SEEN, stated: a0 is not tracked; the read must be `<SST_layer>(a0)` by the
player-code calling convention (a0 = the player SST). Collision_GetType is the one anchor;
every other routine that references Tile_Cache_Collision is listed in the report, and a
sensor path that transfers to one of them is COULD NOT RUN (a second plane select this arm
does not grade). The executed half starts only at self-contained sensor entries; the
handoffs inside PState_Climb / Glide_Collide / Knuckles_Gliding_WallCatch are graded by the
static flow alone (their executed part is the carriers they call, which the entries cover).
"""

import pathlib
import re

import pstate_writers as pw
from pstate_writers import Unmeasurable, Extents, scan_transfers, decode_one, reg_set
from sprite_tilt_gate import Micro, UnsupportedInstruction, SIZE_MASK

ANCHOR = "Collision_GetType"
CACHE = "Tile_Cache_Collision"
NEED_EQUS = ("SST_layer", "SST_x_pos", "SST_y_pos", "SST_angle", "TILE_CACHE_COLL_SIZE",
             "TILE_CACHE_COLS", "TILE_CACHE_COLL_ROWS", "SOLID_ALL")
NEED_SYMS = (ANCHOR, CACHE, "Cache_Left_Col", "Cache_Head_Col", "Cache_Top_Row",
             "Cache_Bottom_Row", "Cache_Origin_Col", "Cache_Origin_Row", "SolidityTable",
             "HeightMaps")

T = "T"                         # unknown
MAX_STATES = 60000


# ---------------------------------------------------------------------------
# Operand helpers (capstone text)
# ---------------------------------------------------------------------------

_SP_REL = re.compile(r"^(?:\$([0-9a-f]+))?\((?:a7|sp)\)$")
_PC_ABS = re.compile(r"^\$([0-9a-f]+)\(pc\)$")
_PC_IDX = re.compile(r"^\$([0-9a-f]+)\(pc, *d([0-7])\.w\)$")
_ABS = re.compile(r"^\$([0-9a-f]+)(\.[wl])?$")
_IND = re.compile(r"^\(a([0-6])\)$")
_IMM = re.compile(r"^#\$?(-?[0-9a-f]+)$")


def _norm(tok):
    return tok.replace("sp", "a7")


def _abs_addr(tok):
    m = _ABS.match(tok)
    if not m:
        return None
    v = int(m.group(1), 16)
    if m.group(2) == ".w" and v & 0x8000:
        v = (v - 0x10000) & 0xFFFFFF
    return v & 0xFFFFFF


def _addr_operand(tok):
    """An address an operand NAMES (pc-relative or absolute), or None."""
    m = _PC_ABS.match(tok)
    if m:
        return int(m.group(1), 16)
    return _abs_addr(tok)


def _imm(tok):
    m = _IMM.match(tok)
    if not m:
        return None
    return int(m.group(1), 16)


def _reg(tok):
    tok = _norm(tok)
    if re.fullmatch(r"[da][0-7]", tok):
        return tok
    return None


def _sz(mn):
    return mn.split(".")[1] if "." in mn else "w"


# ---------------------------------------------------------------------------
# A. The static d3 flow
# ---------------------------------------------------------------------------

def _push(stack, nbytes, tag):
    return None if stack is None else ((nbytes, tag),) + stack


def _pop(stack, nbytes):
    """(tag, stack') — tag only when exactly one cell of nbytes sits on top."""
    if not stack:
        return T, None
    n, tag = stack[0]
    if n == nbytes:
        return tag, stack[1:]
    return T, None


def _drop(stack, nbytes):
    while stack and nbytes > 0:
        n, _ = stack[0]
        if n > nbytes:
            return None
        nbytes -= n
        stack = stack[1:]
    return stack if nbytes == 0 else None


def _peek(stack, off, nbytes):
    if stack is None:
        return T
    at = 0
    for n, tag in stack:
        if at == off and n == nbytes:
            return tag
        if at >= off:
            return T
        at += n
    return T


def jump_table(rom, table, reg_note):
    """Targets of `move.w T(pc,dN.w),dN / jmp T(pc,dN.w)`: signed word offsets from T,
    read until the table reaches the lowest target seen (the cases follow it)."""
    targets, i, low = [], 0, None
    while True:
        a = table + 2 * i
        if low is not None and a >= low:
            break
        if i > 64:
            raise Unmeasurable("jump table at $%06X (%s) did not close within 64 entries"
                               % (table, reg_note))
        off = pw._sext16((rom[a] << 8) | rom[a + 1])
        tgt = table + off
        if tgt <= table:
            raise Unmeasurable("jump table at $%06X has entry %d -> $%06X, not a forward "
                               "case" % (table, i, tgt))
        targets.append(tgt)
        low = tgt if low is None else min(low, tgt)
        i += 1
    return targets


class Flow:
    """Path-sensitive abstract execution of one routine: d0-d7 tags, a0-a6 tags, a
    byte-accurate stack of tagged cells. d tags: ("L", read_pc) / ("E",) / ("K", v) / T.
    a tags: ("A", addr) / ("EA", n) / T. Stack cells: (nbytes, tag|("R", ret)|None)."""

    def __init__(self, rom, ext, layer_off):
        self.rom = rom
        self.ext = ext
        self.layer = layer_off
        self._summ = {}

    def areg_summary(self, addr, depth):
        """Which a-registers the routine at `addr` returns unchanged (a frozenset)."""
        if addr in self._summ:
            return self._summ[addr] or frozenset()
        name = self.ext.name_at(addr)
        ex = self.ext.extent(name) if name else None
        if ex is None or depth > 3:
            return frozenset()
        self._summ[addr] = None
        keep = frozenset()
        try:
            res = self.analyse(ex[0], ex[1], depth + 1)
            if res["returns"]:
                keep = frozenset(n for n in range(7)
                                 if all(r[n] == ("EA", n) for r in res["returns"]))
        except Unmeasurable:
            keep = frozenset()
        self._summ[addr] = keep
        return keep

    def analyse(self, start, end, depth=0):
        d0 = tuple(("E",) if n == 3 else T for n in range(8))
        a0 = tuple(("EA", n) for n in range(7))
        init = (start, d0, a0, ())
        seen = {init}
        work = [init]
        events, returns, visited, notes = [], [], set(), []

        def go(pc, d, a, st):
            s = (pc, d, a, st)
            if s not in seen:
                if len(seen) > MAX_STATES:
                    raise Unmeasurable("the d3 flow over $%06X..$%06X exceeded %d states"
                                       % (start, end, MAX_STATES))
                seen.add(s)
                work.append(s)

        while work:
            pc, d, a, st = work.pop()
            if not (start <= pc < end):
                raise Unmeasurable("flow left $%06X..$%06X at $%06X" % (start, end, pc))
            insn = decode_one(self.rom, pc)
            if insn is None:
                raise Unmeasurable("capstone cannot decode $%06X" % pc)
            visited.add(pc)
            nxt = pc + insn.size
            mn = insn.mnemonic
            base = mn.split(".")[0]
            size = _sz(mn)
            ops = [_norm(o) for o in pw._split_ops(insn.op_str)] if insn.op_str else []
            dl, al = list(d), list(a)

            def fall(dd=None, aa=None, ss=st):
                dd = tuple(dl) if dd is None else dd
                aa = tuple(al) if aa is None else aa
                if nxt >= end:
                    events.append(dict(pc=pc, kind="fallthrough", target=("addr", end),
                                       d3=dd[3], a=aa))
                    return
                go(nxt, dd, aa, ss)

            def transfer(kind, tgt_spec):
                events.append(dict(pc=pc, kind=kind, target=tgt_spec, d3=d[3], a=a))

            if base in ("rts",):
                if st is None:
                    raise Unmeasurable("rts at $%06X with a stack this pass lost" % pc)
                if st and st[0][1] and st[0][1][0] == "R" and st[0][0] == 4:
                    go(st[0][1][1], d, a, st[1:])
                elif not st:
                    returns.append(a)
                else:
                    raise Unmeasurable("rts at $%06X over an unbalanced stack" % pc)
                continue
            if base in ("rte", "rtr", "illegal", "stop", "trap"):
                continue

            if base in ("bra", "jmp", "bsr", "jsr") or base in pw.BCC:
                call = base in ("bsr", "jsr")
                op = ops[0]
                targets = None
                m = _PC_IDX.match(op)
                mi = _IND.match(op)
                if m:
                    targets = jump_table(self.rom, int(m.group(1), 16), "$%06X" % pc)
                elif mi:
                    n = int(mi.group(1))
                    tag = a[n]
                    if tag != T and tag[0] == "A":
                        targets = [tag[1]]
                    elif tag != T and tag[0] == "EA":
                        transfer("call" if call else "tail", ("areg", tag[1]))
                        if call:
                            fall(tuple(T for _ in range(8)), self._after_call(None, a, depth))
                        continue
                    else:
                        transfer("call" if call else "tail", ("unknown", op))
                        if call:
                            fall(tuple(T for _ in range(8)), self._after_call(None, a, depth))
                        continue
                else:
                    t = _addr_operand(op)
                    if t is None:
                        raise Unmeasurable("%s at $%06X: operand %s not resolved"
                                           % (mn, pc, insn.op_str))
                    targets = [t]
                for t in targets:
                    if call and start <= t < end:
                        go(t, d, a, _push(st, 4, ("R", nxt)))
                    elif call:
                        transfer("call", ("addr", t))
                    elif start <= t < end:
                        go(t, d, a, st)
                    else:
                        transfer("tail", ("addr", t))
                if call and not (len(targets) == 1 and start <= targets[0] < end):
                    fall(tuple(T for _ in range(8)),
                         self._after_call(targets[0] if len(targets) == 1 else None, a, depth))
                elif base in pw.BCC:
                    fall()
                continue
            if base.startswith("db"):
                r = _reg(ops[0])
                if r:
                    dl[int(r[1])] = T
                t = _addr_operand(ops[1])
                if t is None or not (start <= t < end):
                    raise Unmeasurable("%s at $%06X leaves the routine" % (mn, pc))
                go(t, tuple(dl), a, st)
                fall()
                continue

            # ---- data movement ----
            if base == "moveq":
                dl[int(ops[1][1])] = ("K", _imm(ops[0]) & 0xFF)
                fall()
                continue
            if base == "lea":
                r = _reg(ops[1])
                if r == "a7":
                    raise Unmeasurable("lea into the stack pointer at $%06X" % pc)
                t = _addr_operand(ops[0])
                al[int(r[1])] = ("A", t) if t is not None else T
                fall()
                continue
            if base == "pea":
                t = _addr_operand(ops[0])
                fall(ss=_push(st, 4, ("A", t) if t is not None else None))
                continue
            if base == "movem":
                src, dst = ops
                nb = 2 if size == "w" else 4
                if dst == "-(a7)":
                    regs = sorted(reg_set(src), key=lambda r: (r[0] != "d", r[1]))
                    ss = st
                    for r in reversed(regs):
                        ss = _push(ss, nb, self._tag(r, dl, al))
                    fall(ss=ss)
                    continue
                if src == "(a7)+":
                    regs = sorted(reg_set(dst), key=lambda r: (r[0] != "d", r[1]))
                    ss = st
                    for r in regs:
                        tag, ss = _pop(ss, nb)
                        self._set(r, tag, dl, al)
                    fall(ss=ss)
                    continue
                for r in reg_set(dst):
                    if r == "a7":
                        raise Unmeasurable("movem into a7 at $%06X" % pc)
                    self._set(r, T, dl, al)
                fall()
                continue
            if base in ("move", "movea"):
                src, dst = ops
                nb = 2 if size in ("b", "w") else 4
                ss = st
                if src == "(a7)+":
                    tag, ss = _pop(ss, nb)
                else:
                    m = _SP_REL.match(src)
                    if m:
                        tag = _peek(ss, int(m.group(1) or "0", 16), nb)
                    elif _reg(src):
                        tag = self._tag(_reg(src), dl, al)
                    elif _imm(src) is not None:
                        tag = ("K", _imm(src) & 0xFF)
                    elif size == "b" and src == "$%x(a0)" % self.layer:
                        tag = ("L", pc)
                    else:
                        tag = T
                if dst == "-(a7)":
                    fall(ss=_push(ss, nb, tag))
                    continue
                r = _reg(dst)
                if r == "a7":
                    raise Unmeasurable("move into the stack pointer at $%06X" % pc)
                if r:
                    self._set(r, tag, dl, al)
                elif "(a7)" in dst:
                    raise Unmeasurable("store through the stack at $%06X (%s)" % (pc, dst))
                fall(ss=ss)
                continue
            if base == "exg":
                r0, r1 = _reg(ops[0]), _reg(ops[1])
                t0, t1 = self._tag(r0, dl, al), self._tag(r1, dl, al)
                self._set(r0, t1, dl, al)
                self._set(r1, t0, dl, al)
                fall()
                continue
            if base in ("addq", "subq", "adda", "suba", "add", "sub") and ops and \
                    ops[-1] == "a7":
                n = _imm(ops[0])
                if n is None:
                    raise Unmeasurable("stack pointer moved by a non-constant at $%06X" % pc)
                if base.startswith("add"):
                    fall(ss=_drop(st, n))
                else:
                    fall(ss=_push(st, n, None))
                continue
            if base in ("clr", "st", "sf") and ops == ["-(a7)"]:
                fall(ss=_push(st, 4 if size == "l" else 2,
                              ("K", 0) if base == "clr" else T))
                continue
            if len(ops) == 2 and ops[0] == "(a7)+" and ops[1] != "-(a7)":
                # an ALU op consuming a stacked value: pop it, the destination is computed
                _tag, ss = _pop(st, 4 if size == "l" else 2)
                w = _reg(ops[1])
                if w == "a7":
                    raise Unmeasurable("%s writes the stack pointer at $%06X" % (mn, pc))
                if w:
                    self._set(w, T, dl, al)
                fall(ss=ss)
                continue
            if any(o in ("-(a7)", "(a7)+") for o in ops):
                raise Unmeasurable("%s %s at $%06X touches the stack in a form this pass "
                                   "does not model" % (mn, insn.op_str, pc))
            if base in pw.READ_ONLY or not ops:
                fall()
                continue
            w = _reg(ops[-1])
            if w == "a7":
                raise Unmeasurable("%s writes the stack pointer at $%06X" % (mn, pc))
            if w:
                self._set(w, ("K", 0) if base == "clr" else T, dl, al)
            fall()
        return dict(events=events, returns=returns, visited=visited, notes=notes)

    def _after_call(self, target, a, depth):
        keep = self.areg_summary(target, depth) if target is not None else frozenset()
        return tuple(a[n] if n in keep else T for n in range(7))

    @staticmethod
    def _tag(r, dl, al):
        return dl[int(r[1])] if r[0] == "d" else (al[int(r[1])] if r != "a7" else T)

    @staticmethod
    def _set(r, tag, dl, al):
        if r[0] == "d":
            dl[int(r[1])] = tag if (tag == T or tag[0] in ("L", "E", "K")) else T
        elif r != "a7":
            al[int(r[1])] = tag if (tag == T or tag[0] in ("A", "EA")) else T


def address_refs(rom, target):
    """Every even offset whose bytes ENCODE lea/pea of `target` (pc-relative or absolute)."""
    out = []
    n = len(rom)
    for o in range(0, n - 3, 2):
        w = (rom[o] << 8) | rom[o + 1]
        if (w & 0xF1FF) == 0x41FA or w == 0x487A:
            if o + 2 + pw._sext16((rom[o + 2] << 8) | rom[o + 3]) == target:
                out.append((o, "lea.pc" if w != 0x487A else "pea.pc"))
        elif ((w & 0xF1FF) == 0x41F9 or w == 0x4879) and o + 6 <= n:
            if int.from_bytes(rom[o + 2:o + 6], "big") & 0xFFFFFF == target:
                out.append((o, "lea.l" if w != 0x4879 else "pea.l"))
    return out


def static_arm(rom, syms, equs):
    """-> dict(carriers, indirect, handoffs, fails, notes, analysed, calls_out)."""
    ext = Extents(syms)
    flow = Flow(rom, ext, equs["SST_layer"])
    anchor = syms[ANCHOR]
    direct = {anchor}                      # F: carriers whose d3 reaches the plane select
    indirect = {}                          # routine addr -> set of a-reg numbers it calls through
    analysed = {}                          # head addr -> flow result
    hits = {}                              # head addr -> set of scanned hit pcs
    scanned = set()

    def head_of(pc):
        name, addr = ext.head_at_or_below(pc)
        if name is None:
            raise Unmeasurable("no routine head below $%06X" % pc)
        return addr

    def scan(member):
        if member in scanned:
            return
        scanned.add(member)
        for o, _form in scan_transfers(rom, member) + address_refs(rom, member):
            h = head_of(o)
            hits.setdefault(h, set()).add(o)
        # a routine that ends exactly at `member` may fall into it
        name, addr = ext.head_at_or_below(member - 1)
        if name is not None:
            ex = ext.extent(name)
            if ex and ex[1] == member:
                hits.setdefault(addr, set())

    scan(anchor)
    handoffs, fails, notes = {}, [], []
    graded_at = set()
    changed = True
    rounds = 0
    while changed:
        rounds += 1
        if rounds > 50:
            raise Unmeasurable("the carrier closure did not converge")
        changed = False
        for h in sorted(hits):
            if h not in analysed:
                name = ext.name_at(h)
                ex = ext.extent(name) if name else None
                if ex is None:
                    raise Unmeasurable("no extent for the routine at $%06X" % h)
                analysed[h] = flow.analyse(ex[0], ex[1])
                changed = True
        for h, res in analysed.items():
            name = ext.name_at(h)
            for ev in res["events"]:
                graded = None
                tk, tv = ev["target"]
                if tk == "addr" and tv in direct:
                    graded = "%s -> %s" % (ev["kind"], ext.name_at(tv) or "$%06X" % tv)
                elif tk == "areg":
                    if h not in indirect or tv not in indirect[h]:
                        if ev["d3"] == ("E",):
                            indirect.setdefault(h, set()).add(tv)
                            changed = True
                            scan(h)
                        continue
                elif tk == "addr" and tv in indirect:
                    via = [n for n in indirect[tv]
                           if ev["a"][n] != T and ev["a"][n][0] == "A"
                           and ev["a"][n][1] in direct]
                    if via:
                        graded = "%s -> %s with a%d = %s" % (
                            ev["kind"], ext.name_at(tv), via[0],
                            ext.name_at(ev["a"][via[0]][1]))
                elif tk == "addr":
                    # a call with an F member's address in a register makes the callee a
                    # candidate carrier-on-that-register: analyse it
                    if any(t != T and t[0] == "A" and t[1] in direct for t in ev["a"]):
                        if tv not in hits:
                            hits.setdefault(tv, set())
                            changed = True
                if graded is None:
                    continue
                key = (h, ev["pc"])
                graded_at.add(key)
                d3 = ev["d3"]
                if d3 != T and d3[0] == "L":
                    if handoffs.get(key, (None,))[0] != "L":
                        handoffs[key] = ("L", d3[1], graded)
                elif d3 == ("E",):
                    if h not in direct:
                        direct.add(h)
                        scan(h)
                        changed = True
                    handoffs.pop(key, None)
                else:
                    msg = ("%s $%06X (%s): d3.b = %s, not the layer byte and not the "
                           "routine's incoming d3" % (name, ev["pc"], graded, _show(d3)))
                    if msg not in fails:
                        fails.append(msg)
    # every scanned hit must be an instruction the flow reached
    for h, pcs in hits.items():
        for o in pcs:
            if o not in analysed[h]["visited"]:
                raise Unmeasurable("%s: a transfer/reference to a sensor carrier at $%06X "
                                   "that the flow never reaches (data, or a path this pass "
                                   "cannot follow)" % (ext.name_at(h), o))
    # handoffs whose routine is itself a carrier are pass-throughs, not handoffs
    handoffs = {k: v for k, v in handoffs.items() if k[0] not in direct}
    graded = {h for (h, _pc) in graded_at if h not in direct}
    calls_out = {}
    for h, res in analysed.items():
        outs = set()
        for ev in res["events"]:
            tk, tv = ev["target"]
            if tk == "addr" and (tv in direct or tv in indirect):
                continue
            if tk == "areg" and h in indirect and tv in indirect[h]:
                continue
            outs.add(ext.name_at(tv) or "$%06X" % tv if tk == "addr" else "%s %s" % (tk, tv))
        calls_out[h] = outs
    return dict(ext=ext, direct=direct, indirect=indirect, handoffs=handoffs, fails=fails,
                graded=graded,
                notes=notes, analysed=analysed, calls_out=calls_out)


def _show(tag):
    if tag == T:
        return "UNKNOWN"
    if tag[0] == "K":
        return "the constant $%02X" % tag[1]
    if tag[0] == "E":
        return "ENTRY"
    return str(tag)


# ---------------------------------------------------------------------------
# Source cross-check
# ---------------------------------------------------------------------------

_LAYER_OP = re.compile(r"(?<![\w.])(?:layer|Sst\.layer|SST_layer)\(")


def _rel(p):
    parts = pathlib.Path(p).parts
    for anchor in ("games", "engine"):
        if anchor in parts:
            return str(pathlib.Path(*parts[parts.index(anchor):]))
    return str(p)


def source_layer_reads(paths):
    """({proc: n register-destination reads}, [flag-only reads])."""
    regs, flags = {}, []
    for p in paths:
        proc, in_use = None, False
        for i, raw in enumerate(p.read_text(errors="replace").splitlines(), 1):
            code = pw._code(raw)
            m = pw._PROC.match(code)
            if m:
                proc = m.group(1)
            if not _LAYER_OP.search(code):
                continue
            mi = pw._INSN.match(code)
            if not mi or mi.group(1) in pw._NOT_INSNS:
                continue
            ops = pw._split_ops(mi.group(3).strip())
            src = [o for o in ops[:-1] if _LAYER_OP.search(o)]
            if mi.group(1) in ("tst", "cmp", "cmpi", "btst"):
                flags.append("%s:%d %s `%s`" % (_rel(p), i, proc, code.strip()))
            elif src and re.fullmatch(r"d[0-7]", ops[-1].strip()):
                regs[proc] = regs.get(proc, 0) + 1
            elif src:
                raise Unmeasurable("%s:%d: `%s` reads the layer into a form this arm does "
                                   "not follow" % (p, i, code.strip()))
    return regs, flags


# ---------------------------------------------------------------------------
# B. Execution
# ---------------------------------------------------------------------------

SST = 0xFFB000
BLOCK = 0xFFB100
STACK_TOP = 0xFFFE00


class Exec(Micro):
    RAM_LO = 0xFF0000

    def __init__(self, rom, cache_lo, cache_hi):
        Micro.__init__(self, rom, SST)
        self.cache = (cache_lo, cache_hi)
        self.cache_reads = []
        self._pending = 2

    def rb(self, addr):
        addr &= 0xFFFFFF
        if self.cache[0] <= addr < self.cache[1]:
            self.cache_reads.append(addr)
        if addr in self.ram:
            return self.ram[addr]
        if addr >= self.RAM_LO:
            return 0
        if addr < len(self.rom):
            return self.rom[addr]
        raise UnsupportedInstruction("read from unmapped address $%06X" % addr)

    def ea(self, tok, size):
        tok = _norm(tok)
        nb = {"b": 1, "w": 2, "l": 4}[size]
        m = re.fullmatch(r"-\(a([0-7])\)", tok)
        if m:
            n = int(m.group(1))
            step = 2 if (n == 7 and nb == 1) else nb
            self.a[n] = (self.a[n] - step) & 0xFFFFFFFF
            return self.a[n] & 0xFFFFFF
        m = re.fullmatch(r"\(a([0-7])\)\+", tok)
        if m:
            n = int(m.group(1))
            step = 2 if (n == 7 and nb == 1) else nb
            was = self.a[n] & 0xFFFFFF
            self.a[n] = (self.a[n] + step) & 0xFFFFFFFF
            return was
        m = re.fullmatch(r"(?:\$([0-9a-f]+)|-\$([0-9a-f]+))?\(a([0-7])\)", tok)
        if m:
            disp = int(m.group(1), 16) if m.group(1) else (-int(m.group(2), 16)
                                                           if m.group(2) else 0)
            return (self.a[int(m.group(3))] + disp) & 0xFFFFFF
        m = re.fullmatch(r"(?:\$([0-9a-f]+))?\(a([0-7]), *d([0-7])\.([wl])\)", tok)
        if m:
            idx = self.d[int(m.group(3))]
            if m.group(4) == "w":
                idx = pw._sext16(idx & 0xFFFF)
            return (self.a[int(m.group(2))] + int(m.group(1) or "0", 16) + idx) & 0xFFFFFF
        m = _PC_ABS.match(tok)
        if m:
            return int(m.group(1), 16)
        m = _PC_IDX.match(tok)
        if m:
            return (int(m.group(1), 16) + pw._sext16(self.d[int(m.group(2))] & 0xFFFF)) \
                & 0xFFFFFF
        v = _abs_addr(tok)
        if v is not None:
            return v
        raise UnsupportedInstruction("operand form not modelled: %r" % tok)

    def get(self, tok, size):
        tok = _norm(tok)
        if _imm(tok) is not None:
            return _imm(tok) & SIZE_MASK[size]
        r = _reg(tok)
        if r:
            return (self.d if r[0] == "d" else self.a)[int(r[1])] & SIZE_MASK[size]
        return self.read(self.ea(tok, size), size)

    def put(self, tok, val, size, addr=None):
        tok = _norm(tok)
        r = _reg(tok)
        if r and r[0] == "d":
            m = SIZE_MASK[size]
            self.d[int(r[1])] = (self.d[int(r[1])] & ~m & 0xFFFFFFFF) | (val & m)
        elif r:
            if size == "w":
                val = pw._sext16(val & 0xFFFF)
            self.a[int(r[1])] = val & 0xFFFFFFFF
        else:
            self.write(self.ea(tok, size) if addr is None else addr, val, size)


def _bits(size):
    return {"b": 8, "w": 16, "l": 32}[size]


def run(cpu, entry, allowed, limit=6000):
    """Run from `entry` to its final rts. Calls may go only to addresses in `allowed`
    (the carriers) or inside the routine. Returns the set of executed pcs."""
    md = pw._md()
    cpu.a[7] = STACK_TOP
    executed = set()
    pc = entry
    for _ in range(limit):
        insn = next(md.disasm(cpu.rom[pc:pc + 10], pc, 1), None)
        if insn is None:
            raise UnsupportedInstruction("cannot decode $%06X" % pc)
        executed.add(pc)
        mn = insn.mnemonic
        base = mn.split(".")[0]
        size = _sz(mn)
        ops = pw._split_ops(insn.op_str) if insn.op_str else []
        nxt = pc + insn.size
        if base == "rts":
            if cpu.a[7] & 0xFFFFFF == STACK_TOP:
                return executed
            pc = cpu.read(cpu.a[7] & 0xFFFFFF, "l") & 0xFFFFFF
            cpu.a[7] += 4
            continue
        if base == "nop":
            pc = nxt
            continue
        if base in ("bra", "jmp", "bsr", "jsr") or base in pw.BCC:
            if base in pw.BCC and not cpu.cond(base[1:]):
                pc = nxt
                continue
            tok = _norm(ops[0])
            mi = re.fullmatch(r"\(a([0-6])\)", tok)
            if mi:
                tgt = cpu.a[int(mi.group(1))] & 0xFFFFFF
            elif _PC_IDX.match(tok):
                tgt = cpu.ea(tok, "w")
            else:
                tgt = _addr_operand(tok)
            if base in ("bsr", "jsr"):
                if not allowed(tgt):
                    raise UnsupportedInstruction(
                        "call at $%06X to $%06X, outside the sensor family and outside "
                        "the routine: it has to be understood before it is executed"
                        % (pc, tgt))
                cpu.a[7] = (cpu.a[7] - 4) & 0xFFFFFFFF
                cpu.write(cpu.a[7] & 0xFFFFFF, nxt, "l")
                cpu.calls.append((pc, tgt))
            pc = tgt
            continue
        if base == "moveq":
            v = _imm(ops[0]) & 0xFF
            v = v - 0x100 if v & 0x80 else v
            cpu.d[int(ops[1][1])] = v & 0xFFFFFFFF
            cpu.logic_flags(v & 0xFFFFFFFF, "l")
        elif base in ("move", "movea"):
            v = cpu.get(ops[0], size)
            if base == "move":
                cpu.logic_flags(v, size)
            cpu.put(ops[1], v, size)
        elif base == "lea":
            cpu.a[int(_norm(ops[1])[1])] = cpu.ea(ops[0], "l")
        elif base == "movem":
            nb = 2 if size == "w" else 4
            src, dst = _norm(ops[0]), _norm(ops[1])
            if dst == "-(a7)":
                regs = sorted(reg_set(src), key=lambda r: (r[0] != "d", r[1]))
                for r in reversed(regs):
                    cpu.a[7] = (cpu.a[7] - nb) & 0xFFFFFFFF
                    v = (cpu.d if r[0] == "d" else cpu.a)[int(r[1])]
                    cpu.write(cpu.a[7] & 0xFFFFFF, v, size)
            elif src == "(a7)+":
                regs = sorted(reg_set(dst), key=lambda r: (r[0] != "d", r[1]))
                for r in regs:
                    v = cpu.read(cpu.a[7] & 0xFFFFFF, size)
                    if nb == 2:
                        v = pw._sext16(v) & 0xFFFFFFFF      # movem.w sign-extends
                    (cpu.d if r[0] == "d" else cpu.a)[int(r[1])] = v
                    cpu.a[7] = (cpu.a[7] + nb) & 0xFFFFFFFF
            else:
                raise UnsupportedInstruction("movem form not modelled at $%06X" % pc)
        elif base in ("tst",):
            cpu.logic_flags(cpu.get(ops[0], size), size)
        elif base in ("cmp", "cmpi", "cmpa"):
            cpu.sub_flags(cpu.get(ops[1], size), cpu.get(ops[0], size), size)
        elif base in ("add", "addi", "addq", "sub", "subi", "subq", "adda", "suba"):
            dst = _norm(ops[1])
            b = cpu.get(ops[0], size)
            if _reg(dst) and dst[0] == "a":
                if size == "w":
                    b = pw._sext16(b)
                n = int(dst[1])
                cpu.a[n] = (cpu.a[n] + (b if base.startswith("add") else -b)) & 0xFFFFFFFF
            else:
                addr = None if _reg(dst) else cpu.ea(dst, size)
                a = cpu.get(dst, size) if addr is None else cpu.read(addr, size)
                r = (cpu.add_flags if base.startswith("add") else cpu.sub_flags)(a, b, size)
                cpu.put(dst, r, size, addr)
        elif base in ("and", "andi", "or", "ori", "eor", "eori"):
            dst = _norm(ops[1])
            addr = None if _reg(dst) else cpu.ea(dst, size)
            a = cpu.get(dst, size) if addr is None else cpu.read(addr, size)
            b = cpu.get(ops[0], size)
            r = a & b if base.startswith("and") else (a | b if base.startswith("or")
                                                       else a ^ b)
            cpu.logic_flags(r, size)
            cpu.put(dst, r, size, addr)
        elif base in ("lsl", "lsr", "asl", "asr", "rol", "ror"):
            if len(ops) != 2 or _imm(ops[0]) is None:
                raise UnsupportedInstruction("shift form not modelled at $%06X" % pc)
            cnt = _imm(ops[0]) or 8
            bits = _bits(size)
            m = SIZE_MASK[size]
            v = cpu.get(ops[1], size)
            if base == "lsl" or base == "asl":
                r = (v << cnt) & m
                c = bool((v >> (bits - cnt)) & 1)
            elif base == "lsr":
                r = v >> cnt
                c = bool((v >> (cnt - 1)) & 1)
            elif base == "asr":
                sv = v - (1 << bits) if v >> (bits - 1) else v
                r = (sv >> cnt) & m
                c = bool((sv >> (cnt - 1)) & 1)
            elif base == "rol":
                cnt %= bits
                r = ((v << cnt) | (v >> (bits - cnt))) & m
                c = bool(r & 1)
            else:
                cnt %= bits
                r = ((v >> cnt) | (v << (bits - cnt))) & m
                c = bool(r >> (bits - 1))
            cpu.logic_flags(r, size)
            cpu.c = c
            cpu.put(ops[1], r, size)
        elif base == "ext":
            r = _norm(ops[0])
            v = cpu.d[int(r[1])]
            if size == "w":
                lo = v & 0xFF
                nv = (lo - 0x100 if lo & 0x80 else lo) & 0xFFFF
                cpu.d[int(r[1])] = (v & 0xFFFF0000) | nv
                cpu.logic_flags(nv, "w")
            else:
                lo = v & 0xFFFF
                nv = pw._sext16(lo) & 0xFFFFFFFF
                cpu.d[int(r[1])] = nv
                cpu.logic_flags(nv, "l")
        elif base in ("neg", "not", "clr"):
            v = cpu.get(ops[0], size)
            if base == "neg":
                r = cpu.sub_flags(0, v, size)
            elif base == "not":
                r = (~v) & SIZE_MASK[size]
                cpu.logic_flags(r, size)
            else:
                r = 0
                cpu.logic_flags(0, size)
            cpu.put(ops[0], r, size)
        elif base in ("btst", "bset", "bclr", "bchg"):
            bit = cpu.get(ops[0], "b")
            dst = _norm(ops[1])
            if _reg(dst):
                bit &= 31
                v = cpu.d[int(dst[1])]
                cpu.z = not (v >> bit) & 1
                if base != "btst":
                    v = v | (1 << bit) if base == "bset" else (
                        v & ~(1 << bit) if base == "bclr" else v ^ (1 << bit))
                    cpu.d[int(dst[1])] = v & 0xFFFFFFFF
            else:
                bit &= 7
                addr = cpu.ea(dst, "b")
                v = cpu.read(addr, "b")
                cpu.z = not (v >> bit) & 1
                if base != "btst":
                    v = v | (1 << bit) if base == "bset" else (
                        v & ~(1 << bit) if base == "bclr" else v ^ (1 << bit))
                    cpu.write(addr, v & 0xFF, "b")
        elif base == "swap":
            n = int(_norm(ops[0])[1])
            v = cpu.d[n]
            cpu.d[n] = ((v >> 16) | (v << 16)) & 0xFFFFFFFF
            cpu.logic_flags(cpu.d[n], "l")
        else:
            raise UnsupportedInstruction("instruction not modelled: %s %s at $%06X"
                                         % (mn, insn.op_str, pc))
        pc = nxt
    raise UnsupportedInstruction("instruction limit from $%06X" % entry)


def fill_attrs(rom, syms, equs):
    """(air, full, partial) attribute bytes from this ROM's own tables: 0; the first attr
    of class SOLID_ALL whose 16 height columns are all 16; the first SOLID_ALL attr whose
    columns are all in 1..15."""
    sol, hm = syms["SolidityTable"], syms["HeightMaps"]
    full = partial = None
    for attr in range(1, 256):
        if rom[sol + attr] != equs["SOLID_ALL"]:
            continue
        cols = [pw._sext8(rom[hm + attr * 16 + i]) for i in range(16)]
        if full is None and all(c == 16 for c in cols):
            full = attr
        if partial is None and all(1 <= c <= 15 for c in cols):
            partial = attr
    if full is None or partial is None:
        raise Unmeasurable("this ROM's SolidityTable/HeightMaps have no %s block of class "
                           "SOLID_ALL" % ("full" if full is None else "partial"))
    return (0, full, partial)


def executed_arm(rom, syms, equs, st, quad_off):
    """Execute every self-contained handoff routine at both layers. -> (fails, notes)."""
    ext = st["ext"]
    carriers = set(st["direct"]) | set(st["indirect"])
    entries = sorted(h for h in st["graded"] if not st["calls_out"][h])
    static_only = sorted(set(st["graded"]) - set(entries))
    fails, notes = [], []
    if not entries:
        raise Unmeasurable("no handoff routine is self-contained, so nothing is executed")
    size = equs["TILE_CACHE_COLL_SIZE"]
    lo = syms[CACHE] & 0xFFFFFF
    attrs = fill_attrs(rom, syms, equs)
    # every call instruction inside every carrier, from the static flow
    need = {}
    for c in carriers:
        res = st["analysed"].get(c)
        name = ext.name_at(c)
        ex = ext.extent(name)
        if res is None:
            res = Flow(rom, ext, equs["SST_layer"]).analyse(ex[0], ex[1])
        for pc in res["visited"]:
            insn = decode_one(rom, pc)
            if insn.mnemonic.split(".")[0] in ("bsr", "jsr"):
                need[pc] = name
    covered = {0: set(), 1: set()}
    runs = 0
    bad = {}
    # a call may go to a carrier, or to a local subroutine inside a carrier or the entry
    spans = [ext.extent(ext.name_at(c)) for c in carriers]
    for h in entries:
        name = ext.name_at(h)
        for layer in (0, 1):
            for attr in attrs:
                for q in range(4):
                    for d2 in range(4):
                        for d7 in (0, 2, 0x80):
                            cpu = Exec(rom, lo, lo + 2 * size)
                            for i in range(2 * size):
                                cpu.ram[lo + i] = attr
                            for sym, v in (("Cache_Left_Col", 0), ("Cache_Head_Col", 0x7FFF),
                                           ("Cache_Top_Row", 0), ("Cache_Bottom_Row", 0x7FFF),
                                           ("Cache_Origin_Col", 0), ("Cache_Origin_Row", 0)):
                                cpu.write(syms[sym] & 0xFFFFFF, v, "w")
                            x, y = 0x100, 0x0C0
                            cpu.write(SST + equs["SST_x_pos"], x, "w")
                            cpu.write(SST + equs["SST_y_pos"], y, "w")
                            cpu.write(SST + equs["SST_layer"], layer, "b")
                            cpu.write(SST + 0x16, 0x12, "b")      # width/height pixels:
                            cpu.write(SST + 0x17, 0x26, "b")      # any non-zero radius
                            cpu.write(BLOCK + quad_off, q, "b")
                            cpu.a[0], cpu.a[4] = SST, BLOCK
                            cpu.d[0], cpu.d[1], cpu.d[2] = x, y, d2
                            cpu.d[3] = 0xA5 ^ layer                # poison: not the layer
                            cpu.d[4] = 1 if d2 & 1 else 0xFFFFFFFF
                            cpu.d[6], cpu.d[7] = 0xFF, d7
                            executed = run(cpu, h, lambda t, sp=spans + [ext.extent(name)]:
                                           any(a <= t < b for a, b in sp))
                            runs += 1
                            for pc in executed:
                                if pc in need:
                                    covered[layer].add(pc)
                            if not cpu.cache_reads:
                                fails.append("VACUOUS: %s at layer %d (attr $%02X, quadrant "
                                             "%d, d2 %d, d7 $%02X) read no collision cell"
                                             % (name, layer, attr, q, d2, d7))
                                continue
                            wrong = [r for r in cpu.cache_reads
                                     if ((r - lo) >= size) != bool(layer)]
                            if wrong:
                                bad.setdefault((name, layer), []).append(
                                    "%s at layer %d (attr $%02X, quadrant %d, d2 %d, d7 "
                                    "$%02X): %d of %d collision reads landed in plane %s "
                                    "(first at $%06X)" % (
                                        name, layer, attr, q, d2, d7, len(wrong),
                                        len(cpu.cache_reads), "B" if not layer else "A",
                                        wrong[0]))
    for (name, layer), rows in sorted(bad.items()):
        fails.append("%d run(s) of %s at layer %d read the wrong plane; first: %s"
                     % (len(rows), name, layer, rows[0]))
    for layer in (0, 1):
        missing = sorted(set(need) - covered[layer])
        if missing:
            fails.append("COVERAGE: at layer %d these carrier call sites never executed: %s"
                         % (layer, ", ".join("%s $%06X" % (need[p], p) for p in missing)))
    notes.append("EXECUTED %d runs over %d self-contained handoff routine(s) [%s], layers "
                 "0/1 x attrs %s x 4 quadrants x 4 directions x 3 policies; every "
                 "Tile_Cache_Collision read checked against the plane the layer names; "
                 "%d carrier call sites covered at both layers"
                 % (runs, len(entries), ", ".join(ext.name_at(h) for h in entries),
                    "/".join("$%02X" % a for a in attrs), len(need)))
    if static_only:
        notes.append("static-only handoff routine(s) (they call outside the sensor family, "
                     "so they are graded by the flow, not executed): %s"
                     % ", ".join("%s (calls %s)" % (ext.name_at(h),
                                                     ", ".join(sorted(st["calls_out"][h]))[:80])
                                 for h in static_only))
    return fails, notes


def check(rom, syms, equs, lst_path, root, quad_off):
    """-> (rc, lines). rc 0 pass, 1 fail, 2 could not run. `quad_off` is
    PlayerBlock.quadrant's offset (layer_line_gate.player_block_layout, from the .emp)."""
    lines = []
    missing = [n for n in NEED_SYMS if n not in syms] + [n for n in NEED_EQUS if n not in equs]
    if missing:
        return 2, ["layer sensor arm: COULD NOT RUN — the listing lacks %s"
                   % ", ".join(missing)]
    try:
        st = static_arm(rom, syms, equs)
        ext = st["ext"]
        if not st["graded"]:
            raise Unmeasurable("no handoff site found: no path hands the layer byte to "
                               "the collision plane select (an empty set is not a pass)")
        reads = {}
        for (h, _pc), (_k, rpc, _g) in st["handoffs"].items():
            reads.setdefault(ext.name_at(h), set()).add(rpc)
        src_regs, src_flags = source_layer_reads(pw.digest_sources(lst_path, root))
        rom_counts = {n: len(v) for n, v in reads.items()}
        mismatch = sorted(set(src_regs) | set(rom_counts))
        mismatch = [n for n in mismatch if src_regs.get(n, 0) != rom_counts.get(n, 0)]
        xfails, xnotes = executed_arm(rom, syms, equs, st, quad_off)
    except (Unmeasurable, UnsupportedInstruction) as exc:
        return 2, ["layer sensor arm: COULD NOT RUN — %s" % exc]
    lines.append("layer sensor arm: plane select %s; carriers (d3 passed through): %s"
                 % (ANCHOR, ", ".join(sorted(ext.name_at(c) for c in st["direct"]
                                             if c != syms[ANCHOR]))
                    + ("; through a register: %s" % ", ".join(
                        "%s (a%s)" % (ext.name_at(h), "/".join(map(str, sorted(v))))
                        for h, v in sorted(st["indirect"].items())) if st["indirect"] else "")))
    lines.append("  DERIVED layer-read set: %d read(s) in %d routine(s), %d graded handoff "
                 "site(s):" % (sum(len(v) for v in reads.values()), len(reads),
                               len(st["handoffs"])))
    for (h, pc), (_k, rpc, g) in sorted(st["handoffs"].items()):
        lines.append("    %-30s read $%06X -> handoff $%06X (%s)" % (ext.name_at(h), rpc, pc, g))
    ref_heads = {ext.head_at_or_below(o)[1]
                 for o, _f in address_refs(rom, syms[CACHE] & 0xFFFFFF)}
    refs = sorted(ext.name_at(h) or "?" for h in ref_heads)
    # a sensor path reaching a SECOND reader of the cache would bypass the graded select
    stray = sorted({"%s -> %s" % (ext.name_at(h), ext.name_at(ev["target"][1]))
                    for h, res in st["analysed"].items() for ev in res["events"]
                    if ev["target"][0] == "addr" and ev["target"][1] in ref_heads
                    and ev["target"][1] != syms[ANCHOR]})
    if stray:
        return 2, ["layer sensor arm: COULD NOT RUN — a sensor path calls a routine that "
                   "references %s other than %s, which this arm does not grade: %s"
                   % (CACHE, ANCHOR, ", ".join(stray))]
    lines.append("  %s is referenced by: %s; only %s is graded as the plane select, and no "
                 "sensor path analysed here transfers to the others"
                 % (CACHE, ", ".join(refs), ANCHOR))
    for f in src_flags:
        lines.append("  not a plane select (flag-only read, not graded): %s" % f)
    lines.extend("  " + n for n in xnotes)
    if st["fails"] or xfails:
        lines.append("  FAIL — a collision sensor does not select its plane from the layer "
                     "byte:")
        lines.extend("    " + f for f in (st["fails"] + xfails)[:20])
        return 1, lines
    if mismatch:
        lines.append("  COULD NOT RUN — the source's register-destination layer reads and "
                     "the ROM's graded reads disagree per proc: %s" % ", ".join(
                         "%s (source %d, ROM %d)" % (n, src_regs.get(n, 0),
                                                     rom_counts.get(n, 0)) for n in mismatch))
        return 2, lines
    lines.append("  layer sensor arm OK")
    return 0, lines
