#!/usr/bin/env python3
"""sprite_tilt_gate.py — prove Player_ApplyTilt's selected frame is a function of the
ground angle, by EXECUTING the built ROM's own bytes.

WHY THIS SHAPE. The claim this parcel makes is not "it assembles" — it is "the sprite's
mapping frame changes with the terrain angle, at the S3K octant boundaries, with facing
folded into the angle in the direction that does not mirror one side". No emulator is
available to this lane, and a gate over shipped level content could not fail anyway
unless that content reaches every octant (it does not — see the coverage note in
docs/research/loops-and-sprite-rotation.md). So the subject here is the ROUTINE, taken
from the ROM as bytes:

    s4[.debug].lst  ->  Player_ApplyTilt's address and extent
    s4[.debug].bin  ->  those bytes
    capstone        ->  an INDEPENDENT decoder (not our assembler's own opinion)
    this file       ->  a strict micro-executor for exactly the forms that decode to
    the model       ->  S3K Animate_Sonic loc_126A4's arithmetic, re-derived

and the two are compared over a sweep of angles, facings, animation cursors and all
three characters' animation tables (read from the same ROM, so the shipped scripts are
in the loop too).

The executor is deliberately NOT a 68000 emulator. It implements one instruction form
per line the routine actually contains and raises UnsupportedInstruction on anything
else, so a future edit that reaches for a new addressing mode fails LOUDLY here instead
of being silently skipped. That is the whole reason it is safe to trust its green.

Usage (the post-sigil gate; see build.sh):

    sprite_tilt_gate.py --lst s4.debug.lst --rom s4.debug.bin \
                        --built-after <unix-ts> --gate

Exit 0 = every comparison matched. Exit 1 with --gate = a mismatch, a stale artifact,
or an instruction the executor does not model.
"""

import argparse
import pathlib
import re
import struct
import sys

# --------------------------------------------------------------------------
# The model — S3K Animate_Sonic, walk/run branch loc_126A4 (sonic3k.asm:24808-24862),
# read first-hand out of /home/volence/sonic_hacks/skdisasm/.
#
#   moveq   #0,d1                       ; d1 = the half-turn flip delta
#   move.b  angle(a0),d0
#   bmi.s   loc_126C8                   ; upper half: no bias
#   beq.s   loc_126C8                   ; exactly flat: no bias
#   subq.b  #1,d0                       ; symmetric round bias
# loc_126C8:
#   move.b  status(a0),d2
#   andi.b  #1,d2                       ; d2 = the facing bit
#   bne.s   loc_126D4                   ; facing LEFT: angle already in sense
#   not.b   d0                          ; facing RIGHT: mirror the angle
# loc_126D4:
#   addi.b  #$10,d0                     ; snap to NEAREST, not floor
#   bpl.s   loc_126DC
#   moveq   #3,d1                       ; upper half-turn -> BOTH flip bits
# loc_126DC:
#   andi.b  #$FC,render_flags(a0)
#   eor.b   d1,d2
#   or.b    d2,render_flags(a0)
#   ...
#   lsr.b   #4,d0
#   andi.b  #6,d0                       ; {0,2,4,6}; doubled once (run) or twice (walk)
#
# Our engine's flip bits are 1 and 2 rather than S3K's 0 and 1 (RF_XFLIP/RF_YFLIP,
# engine/system/constants.emp), so the pair is $06 here and $03 there. The octant
# extraction is spelled `lsr.b #5 / andi.w #3` in ours, which is the same bits 5-6 of the
# biased angle -- `(x >> 4) & 6` is `((x >> 5) & 3) * 2`, and ours multiplies by the block
# length at the end instead of pre-doubling.
# --------------------------------------------------------------------------

TILT_BIAS = 0x10        # +22.5 deg
TILT_SETS = 4           # stored orientations per cycle
RF_XFLIP_BIT = 1        # engine/system/constants.emp
RF_YFLIP_BIT = 2
ST_XFLIP_BIT = 1
FLIP_PAIR = (1 << RF_XFLIP_BIT) | (1 << RF_YFLIP_BIT)   # 0x06 = 180 deg

# Sst offsets (engine/objects/sst.emp) — the executor plants a synthetic SST at these.
SST_RENDER_FLAGS = 0x0E
SST_ANIM = 0x18
SST_ANIM_TABLE = 0x1A
SST_STATUS = 0x1E
SST_ANGLE = 0x1F
SST_ANIM_FRAME = 0x21
SST_MAPPING_FRAME = 0x23

ANIM_WALK = 0
ANIM_RUN = 1

# games/sonic4/player/player_common.emp — the frame geometry, which the gate re-checks
# against the shipped scripts rather than assuming.
TILT_WALK_BASE, TILT_WALK_LEN = 0x01, 8
TILT_RUN_BASE, TILT_RUN_LEN = 0x21, 4

AF_END = 0xFF
AF_SET_FIELD = 0xF7     # $F7+ is a control code; 0..$F6 are frame indices


def model_orientation(angle, facing_left):
    """(block 0..3, flip_delta) — the two halves of one orientation."""
    d = angle & 0xFF
    if not (d & 0x80) and d != 0:
        d = (d - 1) & 0xFF
    if not facing_left:
        d = (~d) & 0xFF
    d = (d + TILT_BIAS) & 0xFF
    flip = FLIP_PAIR if (d & 0x80) else 0
    return (d >> 5) & (TILT_SETS - 1), flip


def model_apply(anim, angle, facing_left, script_frame):
    """Full model: the mapping frame and the render_flags flip bits the routine
    must produce, given the frame byte the running script is sitting on."""
    block, flip = model_orientation(angle, facing_left)
    stride = TILT_WALK_LEN if anim == ANIM_WALK else TILT_RUN_LEN
    frame = (script_frame + block * stride) & 0xFF
    facing = (1 << ST_XFLIP_BIT) if facing_left else 0
    return frame, facing ^ flip


# --------------------------------------------------------------------------
# The listing reader
# --------------------------------------------------------------------------

_SYM = re.compile(r"^ (\S+) : ([0-9A-Fa-f]+) [A-Z] \|")


def parse_lst(path):
    """name -> address, from the sigil listing's symbol block."""
    syms = {}
    for line in path.read_text(errors="replace").splitlines():
        m = _SYM.match(line)
        if m:
            syms.setdefault(m.group(1), int(m.group(2), 16))
    if not syms:
        raise SystemExit("sprite_tilt_gate: no symbols parsed from %s — the listing "
                         "format changed; this gate reads the ' NAME : ADDR C |' block" % path)
    return syms


def routine_extent(syms, name):
    """[start, end) — end is the next symbol strictly above start. The routine's own
    hygienic local labels sit inside it and are skipped."""
    start = syms.get(name)
    if start is None:
        raise SystemExit("sprite_tilt_gate: %s is not in the listing. Either the routine "
                         "was renamed or removed, or the tilt was never built." % name)
    prefix = "$games.sonic4.player_common$%s$" % name
    above = [a for n, a in syms.items()
             if a > start and not n.startswith(prefix)]
    if not above:
        raise SystemExit("sprite_tilt_gate: nothing follows %s in the listing" % name)
    return start, min(above)


# --------------------------------------------------------------------------
# The strict micro-executor
# --------------------------------------------------------------------------

class UnsupportedInstruction(Exception):
    pass


def _split_ops(op_str):
    """Split capstone's operand string on top-level commas ($1(a1, d1.w), d0)."""
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


_RE_IMM = re.compile(r"^#\$?(-?[0-9a-fA-F]+)$")
_RE_D = re.compile(r"^d([0-7])$")
_RE_A = re.compile(r"^a([0-7])$")
_RE_DISP = re.compile(r"^(?:\$([0-9a-fA-F]+))?\(a([0-7])\)$")
_RE_IDX = re.compile(r"^(?:\$([0-9a-fA-F]+))?\(a([0-7]), *d([0-7])\.([wl])\)$")
_RE_ABSW = re.compile(r"^\$([0-9a-fA-F]+)\.w$")
_RE_ABSL = re.compile(r"^\$([0-9a-fA-F]+)\.l$")
_RE_TGT = re.compile(r"^\$([0-9a-fA-F]+)$")


def parse_operand(tok):
    m = _RE_IMM.match(tok)
    if m:
        txt = m.group(1)
        return ("imm", int(txt, 16) if not txt.lstrip("-").isdigit() or "#$" in tok else int(txt, 16))
    m = _RE_D.match(tok)
    if m:
        return ("d", int(m.group(1)))
    m = _RE_A.match(tok)
    if m:
        return ("a", int(m.group(1)))
    m = _RE_DISP.match(tok)
    if m:
        return ("disp", int(m.group(1) or "0", 16), int(m.group(2)))
    m = _RE_IDX.match(tok)
    if m:
        return ("idx", int(m.group(1) or "0", 16), int(m.group(2)), int(m.group(3)), m.group(4))
    m = _RE_ABSW.match(tok)
    if m:
        return ("absw", int(m.group(1), 16))
    m = _RE_ABSL.match(tok)
    if m:
        return ("absl", int(m.group(1), 16))
    m = _RE_TGT.match(tok)
    if m:
        return ("tgt", int(m.group(1), 16))
    raise UnsupportedInstruction("operand form not modelled: %r" % tok)


SIZE_MASK = {"b": 0xFF, "w": 0xFFFF, "l": 0xFFFFFFFF}
SIZE_BITS = {"b": 8, "w": 16, "l": 32}
SIZE_BYTES = {"b": 1, "w": 2, "l": 4}


class Micro:
    """A 68000 subset executor. Every form it accepts is one the routine contains;
    everything else raises. Memory is the ROM plus a sparse RAM overlay."""

    def __init__(self, rom, ram_base):
        self.rom = rom
        self.ram = {}
        self.ram_base = ram_base
        self.d = [0] * 8
        self.a = [0] * 8
        self.n = self.z = self.v = self.c = False
        self.calls = []

    # --- memory ---
    def rb(self, addr):
        addr &= 0xFFFFFF
        if addr in self.ram:
            return self.ram[addr]
        if self.ram_base <= addr < self.ram_base + 0x100:
            return 0                    # the synthetic SST: unwritten fields read 0
        if addr < len(self.rom):
            return self.rom[addr]
        raise UnsupportedInstruction("read from unmapped address $%06X" % addr)

    def wb(self, addr, val):
        self.ram[addr & 0xFFFFFF] = val & 0xFF

    def read(self, addr, size):
        v = 0
        for i in range(SIZE_BYTES[size]):
            v = (v << 8) | self.rb(addr + i)
        return v

    def write(self, addr, val, size):
        nb = SIZE_BYTES[size]
        for i in range(nb):
            self.wb(addr + i, (val >> (8 * (nb - 1 - i))) & 0xFF)

    # --- effective address ---
    def ea_addr(self, op):
        if op[0] == "disp":
            return (self.a[op[2]] + op[1]) & 0xFFFFFF
        if op[0] == "idx":
            _, disp, areg, dreg, isize = op
            idx = self.d[dreg]
            if isize == "w":
                idx &= 0xFFFF
                if idx & 0x8000:
                    idx -= 0x10000
            else:
                idx = idx & 0xFFFFFFFF
                if idx & 0x80000000:
                    idx -= 0x100000000
            return (self.a[areg] + disp + idx) & 0xFFFFFF
        if op[0] in ("absw", "absl"):
            v = op[1]
            if op[0] == "absw" and v & 0x8000:
                v -= 0x10000
            return v & 0xFFFFFF
        raise UnsupportedInstruction("not an addressable operand: %r" % (op,))

    def src(self, op, size):
        if op[0] == "imm":
            return op[1] & SIZE_MASK[size]
        if op[0] == "d":
            return self.d[op[1]] & SIZE_MASK[size]
        if op[0] == "a":
            return self.a[op[1]] & SIZE_MASK[size]
        return self.read(self.ea_addr(op), size)

    def dst_write(self, op, val, size):
        if op[0] == "d":
            mask = SIZE_MASK[size]
            self.d[op[1]] = (self.d[op[1]] & ~mask & 0xFFFFFFFF) | (val & mask)
            return
        if op[0] == "a":
            # address registers always write the full 32 bits (sign-extended for .w)
            if size == "w":
                val &= 0xFFFF
                if val & 0x8000:
                    val -= 0x10000
            self.a[op[1]] = val & 0xFFFFFFFF
            return
        self.write(self.ea_addr(op), val, size)

    # --- flags ---
    def logic_flags(self, res, size):
        bits = SIZE_BITS[size]
        res &= SIZE_MASK[size]
        self.n = bool(res >> (bits - 1))
        self.z = res == 0
        self.v = False
        self.c = False

    def sub_flags(self, a, b, size):
        """a - b (a = destination, b = source), 68000 CMP/SUB semantics."""
        bits = SIZE_BITS[size]
        mask = SIZE_MASK[size]
        r = (a - b) & mask
        sm, dm, rm = (b >> (bits - 1)) & 1, (a >> (bits - 1)) & 1, (r >> (bits - 1)) & 1
        self.n = bool(rm)
        self.z = r == 0
        self.v = bool((sm ^ dm) & (dm ^ rm))
        self.c = bool((sm & ~dm) | (rm & ~dm) | (sm & rm))
        return r

    def add_flags(self, a, b, size):
        bits = SIZE_BITS[size]
        mask = SIZE_MASK[size]
        r = (a + b) & mask
        sm, dm, rm = (b >> (bits - 1)) & 1, (a >> (bits - 1)) & 1, (r >> (bits - 1)) & 1
        self.n = bool(rm)
        self.z = r == 0
        self.v = bool((sm & dm & ~rm) | (~sm & ~dm & rm))
        self.c = bool((sm & dm) | (~rm & dm) | (sm & ~rm))
        return r

    def cond(self, cc):
        return {
            "ra": True,
            "t": True,
            "hi": (not self.c) and (not self.z),
            "ls": self.c or self.z,
            "cc": not self.c, "hs": not self.c,
            "cs": self.c, "lo": self.c,
            "ne": not self.z,
            "eq": self.z,
            "vc": not self.v,
            "vs": self.v,
            "pl": not self.n,
            "mi": self.n,
            "ge": self.n == self.v,
            "lt": self.n != self.v,
            "gt": (self.n == self.v) and not self.z,
            "le": (self.n != self.v) or self.z,
        }[cc]


BRANCHES = {"bra", "bhi", "bls", "bcc", "bhs", "bcs", "blo", "bne", "beq",
            "bvc", "bvs", "bpl", "bmi", "bge", "blt", "bgt", "ble"}


def execute(cpu, prog, entry, stub_targets, limit=400):
    """Run from `entry` until rts. `prog` maps address -> (mnemonic, ops, next_addr)."""
    pc = entry
    steps = 0
    while True:
        steps += 1
        if steps > limit:
            raise UnsupportedInstruction("instruction limit reached — the routine did "
                                         "not return (a branch target left the extent?)")
        if pc not in prog:
            raise UnsupportedInstruction("execution left the routine's extent at $%06X" % pc)
        mnem_full, ops, nxt = prog[pc]
        base = mnem_full.split(".")[0]
        parts = mnem_full.split(".")
        size = parts[1] if len(parts) > 1 else None

        if base == "rts":
            return
        if base == "nop":
            pc = nxt
            continue
        if base in BRANCHES:
            cc = "ra" if base == "bra" else base[1:]
            if cpu.cond(cc):
                pc = ops[0][1]
            else:
                pc = nxt
            continue
        if base == "jsr":
            tgt = cpu.ea_addr(ops[0])
            if tgt not in stub_targets:
                raise UnsupportedInstruction(
                    "call to $%06X, which is not a modelled stub. The gate stubs only "
                    "the calls whose effect on mapping_frame/render_flags is none; a new "
                    "callee has to be understood before it can be ignored." % tgt)
            cpu.calls.append(tgt)
            # Stub: RefreshSpritePieceCount writes frame_off + sprite_piece_count only.
            # It clobbers d2/a1 per its declared contract; poison them so any later
            # dependence on them shows up as a mismatch rather than passing by luck.
            cpu.d[2] = 0xDEADBEEF
            cpu.a[1] = 0xDEAD0000
            pc = nxt
            continue

        if base == "moveq":
            v = ops[0][1] & 0xFF
            if v & 0x80:
                v -= 0x100
            cpu.d[ops[1][1]] = v & 0xFFFFFFFF
            cpu.logic_flags(v & 0xFFFFFFFF, "l")
        elif base == "move":
            v = cpu.src(ops[0], size)
            cpu.logic_flags(v, size)
            cpu.dst_write(ops[1], v, size)
        elif base == "movea":
            v = cpu.src(ops[0], size)
            cpu.dst_write(ops[1], v, size)          # no flags
        elif base == "tst":
            cpu.logic_flags(cpu.src(ops[0], size), size)
        elif base in ("cmpi", "cmp"):
            b = cpu.src(ops[0], size)
            a = cpu.src(ops[1], size)
            cpu.sub_flags(a, b, size)
        elif base in ("andi", "and"):
            r = cpu.src(ops[0], size) & cpu.src(ops[1], size)
            cpu.logic_flags(r, size)
            cpu.dst_write(ops[1], r, size)
        elif base in ("ori", "or"):
            r = cpu.src(ops[0], size) | cpu.src(ops[1], size)
            cpu.logic_flags(r, size)
            cpu.dst_write(ops[1], r, size)
        elif base in ("eori", "eor"):
            r = cpu.src(ops[0], size) ^ cpu.src(ops[1], size)
            cpu.logic_flags(r, size)
            cpu.dst_write(ops[1], r, size)
        elif base == "not":
            r = (~cpu.src(ops[0], size)) & SIZE_MASK[size]
            cpu.logic_flags(r, size)
            cpu.dst_write(ops[0], r, size)
        elif base in ("addi", "addq", "add"):
            b = cpu.src(ops[0], size)
            a = cpu.src(ops[1], size)
            r = cpu.add_flags(a, b, size)
            cpu.dst_write(ops[1], r, size)
        elif base in ("subi", "subq", "sub"):
            b = cpu.src(ops[0], size)
            a = cpu.src(ops[1], size)
            r = cpu.sub_flags(a, b, size)
            cpu.dst_write(ops[1], r, size)
        elif base in ("adda", "suba"):
            b = cpu.src(ops[0], size)
            if size == "w" and b & 0x8000:
                b -= 0x10000
            areg = ops[1][1]
            cpu.a[areg] = (cpu.a[areg] + (b if base == "adda" else -b)) & 0xFFFFFFFF
        elif base in ("lsr", "lsl", "asr", "asl"):
            if ops[0][0] != "imm":
                raise UnsupportedInstruction("register-count shift not modelled")
            cnt = ops[0][1] or 8
            v = cpu.src(ops[1], size)
            bits = SIZE_BITS[size]
            if base in ("lsr", "asr"):
                if base == "asr" and (v >> (bits - 1)) & 1:
                    sv = v - (1 << bits)
                    r = (sv >> cnt) & SIZE_MASK[size]
                else:
                    r = v >> cnt
                cpu.c = bool((v >> (cnt - 1)) & 1) if cnt <= bits else False
            else:
                r = (v << cnt) & SIZE_MASK[size]
                cpu.c = bool((v >> (bits - cnt)) & 1) if cnt <= bits else False
            carry = cpu.c
            cpu.logic_flags(r, size)
            cpu.c = carry
            cpu.dst_write(ops[1], r, size)
        else:
            raise UnsupportedInstruction("instruction not modelled: %s %s"
                                         % (mnem_full, ", ".join(map(str, ops))))
        pc = nxt


def decode(rom, start, end):
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_M68K,
                     capstone.CS_MODE_BIG_ENDIAN | capstone.CS_MODE_M68K_000)
    prog = {}
    listing = []
    for insn in md.disasm(rom[start:end], start):
        ops = [parse_operand(t) for t in _split_ops(insn.op_str)] if insn.op_str else []
        prog[insn.address] = (insn.mnemonic, ops, insn.address + insn.size)
        listing.append((insn.address, insn.bytes.hex(), insn.mnemonic, insn.op_str))
    covered = sum(prog[a][2] - a for a in prog)
    if covered != end - start:
        raise SystemExit("sprite_tilt_gate: capstone decoded %d of %d bytes in "
                         "[$%06X,$%06X) — the extent is not a clean instruction run"
                         % (covered, end - start, start, end))
    return prog, listing


# --------------------------------------------------------------------------
# Script reading — the shipped animation tables, out of the same ROM
# --------------------------------------------------------------------------

def script_frames(rom, table_addr, anim_id):
    """The frame bytes an animation script steps through, in cursor order. The cursor
    is `anim_frame`, a BYTE index into the script starting at 1 (byte 0 is the
    duration), which is exactly what Player_ApplyTilt re-reads."""
    off = struct.unpack_from(">H", rom, table_addr + anim_id * 2)[0]
    body = table_addr + off
    frames = []
    i = 0
    while True:
        b = rom[body + 1 + i]
        if b >= AF_SET_FIELD:
            break
        frames.append((i, b))
        i += 1
        if i > 64:
            raise SystemExit("sprite_tilt_gate: runaway animation script at $%06X" % body)
    if not frames:
        raise SystemExit("sprite_tilt_gate: empty animation script at $%06X" % body)
    return frames


# --------------------------------------------------------------------------
# The sweep
# --------------------------------------------------------------------------

CHARACTERS = ("Ani_Sonic", "Ani_Tails", "Ani_Knuckles")
SST_BASE = 0xFF8000     # anywhere in RAM; the routine only uses displacements off it


def sweep(rom, syms, verbose=False):
    start, end = routine_extent(syms, "Player_ApplyTilt")
    prog, listing = decode(rom, start, end)
    refresh = syms.get("RefreshSpritePieceCount")
    if refresh is None:
        raise SystemExit("sprite_tilt_gate: RefreshSpritePieceCount is not in the listing")

    if verbose:
        for addr, hexb, m, o in listing:
            print("  %06X  %-20s %-9s %s" % (addr, hexb, m, o))

    checks = 0
    fails = []
    bases_seen = {ANIM_WALK: set(), ANIM_RUN: set()}
    frames_selected = set()

    # The angles that matter: every octant boundary and its neighbours, every band
    # centre, and a full 256 sweep on one cursor per (character, anim).
    boundaries = sorted({a for a in range(256)
                         if model_orientation(a, False) != model_orientation((a - 1) & 0xFF, False)
                         or model_orientation(a, True) != model_orientation((a - 1) & 0xFF, True)})
    focus = sorted({(a + d) & 0xFF for a in boundaries for d in (-1, 0, 1)}
                   | {(k * 0x20) & 0xFF for k in range(8)})

    for char in CHARACTERS:
        table = syms.get(char)
        if table is None:
            raise SystemExit("sprite_tilt_gate: %s is not in the listing" % char)
        for anim in (ANIM_WALK, ANIM_RUN):
            frames = script_frames(rom, table, anim)
            lo = TILT_WALK_BASE if anim == ANIM_WALK else TILT_RUN_BASE
            hi = lo + (TILT_WALK_LEN if anim == ANIM_WALK else TILT_RUN_LEN) - 1
            for cursor, fb in frames:
                bases_seen[anim].add(fb)
                if not (lo <= fb <= hi):
                    fails.append("%s anim %d cursor %d: script frame $%02X is outside "
                                 "block 0 ($%02X-$%02X) — the tilt would index into an "
                                 "unrelated frame" % (char, anim, cursor, fb, lo, hi))
            for cursor, fb in frames:
                angles = range(256) if cursor == frames[0][0] else focus
                for angle in angles:
                    for facing_left in (False, True):
                        cpu = Micro(rom, SST_BASE)
                        cpu.a[0] = SST_BASE
                        status = (1 << ST_XFLIP_BIT) if facing_left else 0
                        cpu.wb(SST_BASE + SST_ANIM, anim)
                        cpu.wb(SST_BASE + SST_ANGLE, angle)
                        cpu.wb(SST_BASE + SST_STATUS, status)
                        cpu.wb(SST_BASE + SST_ANIM_FRAME, cursor)
                        # AnimateSprite's state as it leaves it: the untilted frame,
                        # and render_flags carrying facing with the flip pair cleared.
                        cpu.wb(SST_BASE + SST_MAPPING_FRAME, fb)
                        cpu.wb(SST_BASE + SST_RENDER_FLAGS, status)
                        cpu.write(SST_BASE + SST_ANIM_TABLE, table, "l")
                        try:
                            execute(cpu, prog, start, {refresh})
                        except UnsupportedInstruction as exc:
                            raise SystemExit(
                                "sprite_tilt_gate: the executor cannot model the routine "
                                "as built — %s\n  (this is a LOUD stop, not a skip: the "
                                "gate refuses to report green over an instruction it did "
                                "not execute)" % exc)
                        got_frame = cpu.rb(SST_BASE + SST_MAPPING_FRAME)
                        got_flags = cpu.rb(SST_BASE + SST_RENDER_FLAGS)
                        want_frame, want_flags = model_apply(anim, angle, facing_left, fb)
                        checks += 1
                        frames_selected.add(want_frame)
                        if (got_frame, got_flags) != (want_frame, want_flags):
                            fails.append(
                                "%s anim=%d cursor=%d angle=$%02X facing=%s: ROM gave "
                                "frame $%02X flags $%02X, model wants frame $%02X flags $%02X"
                                % (char, anim, cursor, angle,
                                   "L" if facing_left else "R",
                                   got_frame, got_flags, want_frame, want_flags))
                            if len(fails) > 12:
                                return checks, fails, frames_selected, listing

    # The routine must have called RefreshSpritePieceCount on the tilting path — the
    # H1 frame cache goes stale without it and the DEBUG staleness assert fires.
    cpu = Micro(rom, SST_BASE)
    cpu.a[0] = SST_BASE
    cpu.wb(SST_BASE + SST_ANIM, ANIM_WALK)
    cpu.wb(SST_BASE + SST_ANGLE, 0x40)
    cpu.wb(SST_BASE + SST_ANIM_FRAME, 0)
    cpu.wb(SST_BASE + SST_MAPPING_FRAME, TILT_WALK_BASE)
    cpu.write(SST_BASE + SST_ANIM_TABLE, syms["Ani_Sonic"], "l")
    execute(cpu, prog, start, {refresh})
    if refresh not in cpu.calls:
        fails.append("the tilting path did not call RefreshSpritePieceCount — "
                     "Sst.frame_off and sprite_piece_count would go stale against the "
                     "frame the tilt just selected")

    # A non-tilting animation must leave BOTH fields exactly as AnimateSprite set them.
    for anim in (ANIM_RUN + 1, 0x0A):
        cpu = Micro(rom, SST_BASE)
        cpu.a[0] = SST_BASE
        cpu.wb(SST_BASE + SST_ANIM, anim)
        cpu.wb(SST_BASE + SST_ANGLE, 0x40)          # steep: would tilt if it were walk
        cpu.wb(SST_BASE + SST_STATUS, 1 << ST_XFLIP_BIT)
        cpu.wb(SST_BASE + SST_MAPPING_FRAME, 0x9D)  # a Skid frame
        cpu.wb(SST_BASE + SST_RENDER_FLAGS, 1 << ST_XFLIP_BIT)
        cpu.write(SST_BASE + SST_ANIM_TABLE, syms["Ani_Sonic"], "l")
        execute(cpu, prog, start, {refresh})
        if cpu.rb(SST_BASE + SST_MAPPING_FRAME) != 0x9D:
            fails.append("anim %d (no tilted art) had its mapping_frame moved to $%02X"
                         % (anim, cpu.rb(SST_BASE + SST_MAPPING_FRAME)))
        if cpu.rb(SST_BASE + SST_RENDER_FLAGS) != (1 << ST_XFLIP_BIT):
            fails.append("anim %d (no tilted art) had its render_flags rewritten to $%02X"
                         % (anim, cpu.rb(SST_BASE + SST_RENDER_FLAGS)))
        checks += 1

    return checks, fails, frames_selected, listing


# --------------------------------------------------------------------------
# The committed cut — so the PRE-BUILD pytest lane can run the same sweep.
#
# build.sh's pytest lane runs BEFORE sigil, so a unit test that opened s4.debug.bin
# would measure whatever a previous build (or a different sigil profile) left on disk.
# That exact failure is documented at build.sh:61-72 and it happened twice. So the unit
# tests run over a COMMITTED cut of a real ROM, and this gate — which does run on the
# fresh artifact — additionally checks that the cut is still the routine, naming a stale
# fixture rather than letting the unit tests stay green against the past.
#
# Regenerate with:  sprite_tilt_gate.py --lst s4.debug.lst --rom s4.debug.bin \
#                       --emit-fixture tools/fixtures/sprite_tilt_cut.json
# --------------------------------------------------------------------------

FIXTURE_SLAB = 0x100        # bytes captured from each animation table's base


FIXTURE_NOTE = (
    "Cuts of real ROMs, one per build shape. KEYED BY SHAPE because the routine is NOT "
    "byte-identical across them: it lands at a different address and its "
    "`jsr RefreshSpritePieceCount` is an absolute-short operand, so the DEBUG island "
    "moves the callee and with it four bytes of this routine. A single cut would have "
    "been checkable in one shape and permanently stale in the other. Regenerate with "
    "sprite_tilt_gate.py --emit-fixture (it merges the shape it was given); "
    "--fixture checks the cut is still the routine, so a stale one is a named failure."
)


def _shape_key(lst_path):
    return pathlib.Path(lst_path).name


def build_fixture(rom, syms, lst_path, existing=None):
    import json
    start, end = routine_extent(syms, "Player_ApplyTilt")
    slabs = {c: {"addr": syms[c], "bytes": rom[syms[c]:syms[c] + FIXTURE_SLAB].hex()}
             for c in CHARACTERS}
    doc = existing or {"_note": FIXTURE_NOTE, "shapes": {}}
    doc["_note"] = FIXTURE_NOTE
    doc.setdefault("shapes", {})[_shape_key(lst_path)] = {
        "routine": {"name": "Player_ApplyTilt", "addr": start,
                    "bytes": rom[start:end].hex()},
        "refresh_addr": syms["RefreshSpritePieceCount"],
        "anim_tables": slabs,
    }
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def _read_fixture(path):
    import json
    doc = json.loads(pathlib.Path(path).read_text())
    if "shapes" not in doc:
        raise SystemExit("sprite_tilt_gate: %s predates the shape-keyed format; "
                         "regenerate it with --emit-fixture" % path)
    return doc


def fixture_shapes(path):
    return sorted(_read_fixture(path)["shapes"])


def load_fixture(path, shape=None):
    """Rebuild a sparse ROM + symbol table from one shape's committed cut."""
    doc = _read_fixture(path)
    if shape is None:
        shape = sorted(doc["shapes"])[0]
    fx = doc["shapes"][shape]
    rb = bytes.fromhex(fx["routine"]["bytes"])
    rom = bytearray(max(fx["routine"]["addr"] + len(rb),
                        max(s["addr"] + FIXTURE_SLAB
                            for s in fx["anim_tables"].values())))
    rom[fx["routine"]["addr"]:fx["routine"]["addr"] + len(rb)] = rb
    for s in fx["anim_tables"].values():
        b = bytes.fromhex(s["bytes"])
        rom[s["addr"]:s["addr"] + len(b)] = b
    syms = {"Player_ApplyTilt": fx["routine"]["addr"],
            "RefreshSpritePieceCount": fx["refresh_addr"],
            "_end": fx["routine"]["addr"] + len(rb)}
    for name, s in fx["anim_tables"].items():
        syms[name] = s["addr"]
    return bytes(rom), syms


def check_fixture(rom, syms, path, lst_path):
    """Every byte of THIS SHAPE's committed cut must still be what the fresh ROM holds."""
    doc = _read_fixture(path)
    shape = _shape_key(lst_path)
    if shape not in doc["shapes"]:
        return ["no cut committed for shape %r (have: %s) — the pre-build unit tests "
                "cover the other shape(s) only" % (shape, ", ".join(sorted(doc["shapes"])))]
    fx = doc["shapes"][shape]
    problems = []
    start, end = routine_extent(syms, "Player_ApplyTilt")
    if fx["routine"]["addr"] != start:
        problems.append("routine moved: fixture $%06X, listing $%06X"
                        % (fx["routine"]["addr"], start))
    elif fx["routine"]["bytes"] != rom[start:end].hex():
        problems.append("routine bytes differ (fixture %d B, live %d B) — the tilt was "
                        "edited without refreshing the cut"
                        % (len(fx["routine"]["bytes"]) // 2, end - start))
    if fx["refresh_addr"] != syms["RefreshSpritePieceCount"]:
        problems.append("RefreshSpritePieceCount moved: fixture $%06X, listing $%06X"
                        % (fx["refresh_addr"], syms["RefreshSpritePieceCount"]))
    for name, s in fx["anim_tables"].items():
        if s["addr"] != syms.get(name):
            problems.append("%s moved: fixture $%06X, listing $%06X"
                            % (name, s["addr"], syms.get(name, -1)))
        elif rom[s["addr"]:s["addr"] + FIXTURE_SLAB].hex() != s["bytes"]:
            problems.append("%s's script bytes changed" % name)
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lst", required=True)
    ap.add_argument("--rom", required=True)
    ap.add_argument("--fixture", help="committed cut to check for staleness")
    ap.add_argument("--emit-fixture", help="write a fresh cut to this path and exit")
    ap.add_argument("--built-after", type=int, default=None,
                    help="unix timestamp; the listing and ROM must both post-date it")
    ap.add_argument("--gate", action="store_true", help="exit 1 on failure")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    lst, rom_path = pathlib.Path(args.lst), pathlib.Path(args.rom)
    for p in (lst, rom_path):
        if not p.exists():
            print("sprite_tilt_gate: %s is missing" % p, file=sys.stderr)
            return 1 if args.gate else 0

    if args.built_after is not None:
        for p in (lst, rom_path):
            age = int(p.stat().st_mtime) - args.built_after
            if age < 0:
                print("sprite_tilt_gate: %s predates this build by %ds — the gate would "
                      "measure a PREVIOUS artifact" % (p, -age), file=sys.stderr)
                return 1 if args.gate else 0

    rom = rom_path.read_bytes()
    syms = parse_lst(lst)

    if args.emit_fixture:
        import json
        out = pathlib.Path(args.emit_fixture)
        prev = json.loads(out.read_text()) if out.exists() else None
        if prev is not None and "shapes" not in prev:
            prev = None                 # pre-shape-key format: start over
        out.write_text(build_fixture(rom, syms, args.lst, prev))
        print("sprite_tilt_gate: wrote %s (shapes: %s)"
              % (args.emit_fixture, ", ".join(fixture_shapes(out))))
        return 0

    stale = check_fixture(rom, syms, args.fixture, args.lst) if args.fixture else []

    checks, fails, frames, listing = sweep(rom, syms, args.verbose)

    start, end = routine_extent(syms, "Player_ApplyTilt")
    print("sprite_tilt_gate [%s]:" % lst.name)
    print("  Player_ApplyTilt $%06X-$%06X (%d bytes, %d instructions)"
          % (start, end - 1, end - start, len(listing)))
    print("  %d ROM executions compared against the S3K model (Animate_Sonic loc_126A4)"
          % checks)
    print("  distinct mapping frames the sweep selected: %d  ($%02X-$%02X)"
          % (len(frames), min(frames), max(frames)))
    if args.fixture:
        if stale:
            print("  FIXTURE STALE (%s) — the pre-build unit tests are running over a "
                  "cut that is no longer this routine:" % args.fixture)
            for p in stale:
                print("    " + p)
            print("    refresh: tools/sprite_tilt_gate.py --lst %s --rom %s "
                  "--emit-fixture %s" % (args.lst, args.rom, args.fixture))
        else:
            print("  fixture: %s — routine and all three script slabs re-found byte-identical"
                  % pathlib.Path(args.fixture).name)
    if fails or stale:
        if fails:
            print("  FAIL — %d mismatch(es):" % len(fails))
            for f in fails[:12]:
                print("    " + f)
        return 1 if args.gate else 0
    print("  OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
