#!/usr/bin/env python3
"""loop_crossover_gate.py — prove the loop crossover is CONSUMED, by executing the
built ROM's own bytes.

WHY THIS SHAPE. `docs/LOOP_CROSSOVER_ENCODING.md` closed its bake half by watching a
painted mark travel into `crossover.bin` and reading the value back out of the ROM at
the listing's address. That proves the byte is READABLE. It does not prove anything
reads it, and the anchor says so in those words (§5 row 13: "a painted crossover moves
ROM bytes and does not move a player"). The read half's claim is the other one — that
the byte in `CrossoverTable` DECIDES a player's collision plane — and nothing in the
shipped tree can demonstrate it:

  * every cell of every shipped act holds XOVER_NONE (anchor §2.1: all 18 plane files,
    all 65,536 cells each), so a correct read site and a deleted one produce the same
    ROM, the same CRC, and the same recorded play. A gate over content is vacuous here
    BY CONSTRUCTION, which is the whole subject of the anchor's §8.1;
  * there is no loop geometry anywhere in OJZ act 1 (anchor §0), so there is nothing to
    run a player through even by hand.

So the subject is the ROUTINE, taken from the build as bytes:

    s4[.debug].lst  ->  Player_LoopCrossover's and Collision_GetType's extents, the
                        RAM symbols the lookup reads, and the EQU block carrying
                        XOVER_* / LAYER_PATH_* / TILE_CACHE_* out of the .emp sources
    s4[.debug].bin  ->  those routines' bytes AND the shipped CrossoverTable itself
    capstone        ->  an INDEPENDENT decoder, not our assembler's opinion
    this file       ->  a strict micro-executor for exactly the forms they decode to
    the model       ->  layer' = layer if v == XOVER_NONE else v - XOVER_LAYER_BIAS,
                        with v = CrossoverTable[attr of the cell, on the player's own
                        plane] — the anchor's §3.2 table and §6 change (5)

THE ONE EXPERIMENT THAT SEPARATES "READABLE" FROM "CONSUMED". Every other input held
fixed, the ONLY thing varied is one byte of the ROM image at `CrossoverTable + attr`.
If the layer byte follows it, the table is consumed; if it does not, the read site is
decorative. The shipped table is all zeroes, so that value is also the control: the
unmodified ROM must leave the layer alone, and it is the modification that moves it.
The `--gate` run reports both halves.

`Collision_GetType` is EXECUTED, not stubbed. Stubbing it would leave the interesting
half — that the byte the routine indexes with is the attr of the cell the player is
standing in, on the plane the player is on — asserted rather than demonstrated. It is
also what lets the whole sweep avoid re-deriving the cache's addressing: the tests fill
a WHOLE collision plane with one attr byte and let the routine pick its own cell, so no
address arithmetic in this file can accidentally agree with a bug in that routine.

THE EDGE TRIGGER gets its own family, because it has a wrong version that passes a
naive test (anchor §6 change 4). Firing on "the mark became non-zero" also does not
re-fire while you stand still, so standing still proves nothing on its own. The two
tests that discriminate are:

  * TWO-WAY PING-PONG. The ordinary loop pair of §3.3 — plane A says TO_B at the same
    cell where plane B says TO_A. A trigger that re-arms when the layer changes reads
    the OTHER plane's word on the very next frame and flips back, forever. This gate
    runs that exact cell twice and requires the second frame to write NOTHING.
  * SUB-CELL MOTION. Moving within one cell must not re-fire, at every offset inside
    it; moving to the next cell must. That brackets the quantisation from both sides,
    so a trigger that is too fine (re-fires inside a cell, which for a two-way pair is
    the ping-pong again) and one that is too coarse (steps over a marked cell) both
    fail.

The executor is deliberately NOT a 68000 emulator. It implements one instruction form
per line these two routines contain and raises on anything else, so a future edit
reaching for a new addressing mode stops the build instead of being silently skipped.
That refusal is the only reason its green is worth anything.

Usage (the post-sigil gate; see build.sh):

    loop_crossover_gate.py --lst s4.debug.lst --rom s4.debug.bin \
                           --built-after <unix-ts> \
                           --fixture tools/fixtures/loop_crossover_cut.json --gate

Exit 0 = every comparison matched. Exit 1 with --gate = a mismatch, a stale artifact,
or an instruction the executor does not model.
"""

import argparse
import json
import pathlib
import re
import sys

TOOLS = pathlib.Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

# The micro-CPU primitives are shared with the sprite-tilt and insta-shield gates
# rather than re-implemented: same memory model, same flag arithmetic, same operand
# grammar, same "raise on anything not modelled" contract. Only the executor LOOP
# differs, because this subject makes a real CALL and needs a real stack.
from sprite_tilt_gate import (  # noqa: E402
    Micro, UnsupportedInstruction, _split_ops, parse_operand,
    SIZE_MASK, SIZE_BITS,
    normalize_stream, stream_diff, unresolved_note,
)

READ_SITE = "Player_LoopCrossover"
LOOKUP = "Collision_GetType"

_SYM = re.compile(r"^ ([A-Za-z_$][\w$.]*) : ([0-9A-Fa-f]+) [A-Z] \|")
_EQU = re.compile(r"^EQU ([A-Za-z_][\w]*) = \$([0-9A-Fa-f]+)\s*$")

# Every name this gate refuses to substitute a literal for. Symbols place the
# synthetic world; equates carry the encoding and the cache geometry out of
# games/sonic4/config/constants.emp and engine/system/constants.emp.
NEED_SYMS = (READ_SITE, LOOKUP, "CrossoverTable", "SolidityTable",
             "Tile_Cache_Collision", "Cache_Left_Col", "Cache_Head_Col",
             "Cache_Top_Row", "Cache_Bottom_Row", "Cache_Origin_Col",
             "Cache_Origin_Row")
NEED_EQUS = ("XOVER_NONE", "XOVER_TO_A", "XOVER_TO_B", "XOVER_LAYER_BIAS",
             "LAYER_PATH_A", "LAYER_PATH_B", "COLL_CELL_W", "COLL_CELL_H",
             "CTYPE_AIR", "SST_x_pos", "SST_y_pos", "SST_layer",
             "TILE_CACHE_COLS", "TILE_CACHE_ROWS", "TILE_CACHE_COLL_SIZE")


def parse_lst(path):
    syms, equs = {}, {}
    for line in pathlib.Path(path).read_text(errors="replace").splitlines():
        m = _SYM.match(line)
        if m:
            syms.setdefault(m.group(1), int(m.group(2), 16))
            continue
        m = _EQU.match(line)
        if m:
            equs.setdefault(m.group(1), int(m.group(2), 16))
    missing = [n for n in NEED_SYMS if n not in syms]
    if missing:
        raise SystemExit(
            "loop_crossover_gate: %s carries no symbol for %s. Either the read site "
            "was renamed or removed, or the listing format changed (this gate reads "
            "the ' NAME : ADDR C |' block)." % (path, ", ".join(missing)))
    missing = [n for n in NEED_EQUS if n not in equs]
    if missing:
        raise SystemExit(
            "loop_crossover_gate: %s carries no equate for %s — this gate takes the "
            "crossover encoding and the cache geometry from the build's own constants "
            "and will not substitute a literal." % (path, ", ".join(missing)))
    return syms, equs


def routine_extent(syms, name):
    """[start, end) — end is the next symbol strictly above start. The routine's own
    hygienic local labels sit inside it and are skipped."""
    start = syms[name]
    marker = "$%s$" % name
    above = [a for n, a in syms.items() if a > start and marker not in n]
    if not above:
        raise SystemExit("loop_crossover_gate: nothing follows %s in the listing" % name)
    return start, min(above)


# --------------------------------------------------------------------------
# The model — the anchor's §3.2 value table and §6 change (5), and nothing else
# --------------------------------------------------------------------------

def model(layer, xover_value, k):
    """What the encoding says must happen. `k` carries the constants the build was
    assembled with, so this cannot drift from them by being written down twice."""
    if xover_value == k["XOVER_NONE"]:
        return layer                       # the cell is not a crossover
    return (xover_value - k["XOVER_LAYER_BIAS"]) & 0xFF


# --------------------------------------------------------------------------
# The strict micro-executor
# --------------------------------------------------------------------------

BRANCHES = {"bra", "bhi", "bls", "bcc", "bhs", "bcs", "blo", "bne", "beq",
            "bvc", "bvs", "bpl", "bmi", "bge", "blt", "bgt", "ble"}

_RE_PREDEC = re.compile(r"^-\(a([0-7])\)$")
_RE_POSTINC = re.compile(r"^\(a([0-7])\)\+$")


def operand(tok):
    """parse_operand plus the two stack forms the shared grammar does not carry."""
    m = _RE_PREDEC.match(tok)
    if m:
        return ("predec", int(m.group(1)))
    m = _RE_POSTINC.match(tok)
    if m:
        return ("postinc", int(m.group(1)))
    return parse_operand(tok)


class Cpu(Micro):
    """Micro with a real work-RAM window and the two stack addressing modes.

    Micro's own memory model is "the ROM, plus a 256-byte synthetic SST, plus writes".
    The lookup this gate executes reads the tile cache and six camera words out of the
    68000's work RAM, so the window is widened to all of $FF0000-$FFFFFF, reading zero
    where nothing was written. Reads anywhere else still raise — an address neither in
    the ROM nor in work RAM means the routine went somewhere this gate did not model.
    """

    RAM_LO = 0xFF0000

    def rb(self, addr):
        addr &= 0xFFFFFF
        if addr in self.ram:
            return self.ram[addr]
        if addr >= self.RAM_LO:
            return 0
        if addr < len(self.rom):
            return self.rom[addr]
        raise UnsupportedInstruction("read from unmapped address $%06X" % addr)

    def ea_addr(self, op):
        if op[0] == "predec":
            self.a[op[1]] = (self.a[op[1]] - self._pending) & 0xFFFFFFFF
            return self.a[op[1]] & 0xFFFFFF
        if op[0] == "postinc":
            was = self.a[op[1]] & 0xFFFFFF
            self.a[op[1]] = (self.a[op[1]] + self._pending) & 0xFFFFFFFF
            return was
        return Micro.ea_addr(self, op)


class Trace:
    """Everything the run observed, so a test can assert on absence as well as value."""

    def __init__(self):
        self.writes = []          # (addr, size) in program order
        self.called = []
        self.steps = 0


def _sized(cpu, size):
    cpu._pending = {"b": 2, "w": 2, "l": 4}[size]   # -(a7)/(a7)+ are word-aligned


def execute(cpu, prog, entry, extents, trace, limit=600):
    """Run from `entry` until the rts that returns past the entry frame. `prog` maps
    address -> (mnemonic, ops, next). `extents` is the set of address ranges whose
    bytes were decoded — a transfer outside all of them raises."""
    ret = ["<end>"]
    pc = entry
    while True:
        trace.steps += 1
        if trace.steps > limit:
            raise UnsupportedInstruction(
                "instruction limit reached — %s did not return" % READ_SITE)
        if pc not in prog:
            raise UnsupportedInstruction(
                "execution left the decoded extents at $%06X — a callee this gate does "
                "not model, or a branch into the middle of an instruction" % pc)
        mnem_full, ops, nxt = prog[pc]
        parts = mnem_full.split(".")
        base, size = parts[0], (parts[1] if len(parts) > 1 else None)
        _sized(cpu, size or "w")

        if base == "rts":
            back = ret.pop()
            if back == "<end>":
                return
            pc = back
            continue
        if base in BRANCHES:
            cc = "ra" if base == "bra" else base[1:]
            pc = ops[0][1] if cpu.cond(cc) else nxt
            continue
        if base in ("jsr", "bsr"):
            tgt = ops[0][1] if ops[0][0] in ("tgt", "absw", "absl") else None
            if tgt is None:
                raise UnsupportedInstruction("%s with an unmodelled operand" % mnem_full)
            if tgt in ("absw",) and tgt & 0x8000:
                tgt -= 0x10000
            if not any(lo <= tgt < hi for lo, hi in extents):
                raise UnsupportedInstruction(
                    "call to $%06X, which is outside every routine this gate decoded. "
                    "A new callee has to be understood before its effect on the layer "
                    "byte can be assumed to be none." % tgt)
            trace.called.append(tgt)
            ret.append(nxt)
            pc = tgt
            continue

        if base == "moveq":
            v = ops[0][1] & 0xFF
            if v & 0x80:
                v -= 0x100
            cpu.d[ops[1][1]] = v & 0xFFFFFFFF
            cpu.logic_flags(v & 0xFFFFFFFF, "l")
        elif base == "swap":
            r = ops[0][1]
            v = cpu.d[r] & 0xFFFFFFFF
            v = ((v >> 16) | (v << 16)) & 0xFFFFFFFF
            cpu.d[r] = v
            cpu.logic_flags(v, "l")
        elif base == "lea":
            cpu.a[ops[1][1]] = cpu.ea_addr(ops[0]) & 0xFFFFFFFF     # no flags
        elif base == "move":
            v = cpu.src(ops[0], size)
            cpu.logic_flags(v, size)
            if ops[1][0] in ("disp", "idx", "absw", "absl", "predec", "postinc"):
                trace.writes.append((cpu.ea_addr(ops[1]), size))
                cpu.write(trace.writes[-1][0], v, size)
            else:
                cpu.dst_write(ops[1], v, size)
        elif base == "movea":
            cpu.dst_write(ops[1], cpu.src(ops[0], size), size)      # no flags
        elif base == "tst":
            cpu.logic_flags(cpu.src(ops[0], size), size)
        elif base in ("cmpi", "cmp"):
            cpu.sub_flags(cpu.src(ops[1], size), cpu.src(ops[0], size), size)
        elif base in ("andi", "and", "ori", "or", "eori", "eor"):
            a, b = cpu.src(ops[1], size), cpu.src(ops[0], size)
            r = {"andi": a & b, "and": a & b, "ori": a | b, "or": a | b,
                 "eori": a ^ b, "eor": a ^ b}[base]
            cpu.logic_flags(r, size)
            cpu.dst_write(ops[1], r, size)
        elif base in ("addi", "addq", "add", "subi", "subq", "sub"):
            b, a = cpu.src(ops[0], size), cpu.src(ops[1], size)
            r = (cpu.add_flags if base.startswith("add") else cpu.sub_flags)(a, b, size)
            if ops[1][0] in ("disp", "idx", "absw", "absl"):
                trace.writes.append((cpu.ea_addr(ops[1]), size))
            cpu.dst_write(ops[1], r, size)
        elif base in ("lsr", "lsl", "asr", "asl"):
            if ops[0][0] != "imm":
                raise UnsupportedInstruction("register-count shift not modelled")
            cnt = ops[0][1] or 8
            v = cpu.src(ops[1], size)
            bits = SIZE_BITS[size]
            if base in ("lsr", "asr"):
                r = (v >> cnt) if not (base == "asr" and (v >> (bits - 1)) & 1) \
                    else ((v - (1 << bits)) >> cnt) & SIZE_MASK[size]
            else:
                r = (v << cnt) & SIZE_MASK[size]
            cpu.logic_flags(r, size)
            cpu.dst_write(ops[1], r, size)
        else:
            raise UnsupportedInstruction("instruction not modelled: %s %s"
                                         % (mnem_full, ", ".join(map(str, ops))))
        pc = nxt


def decode(rom, spans):
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_M68K,
                     capstone.CS_MODE_BIG_ENDIAN | capstone.CS_MODE_M68K_000)
    prog, listing = {}, []
    for start, end in spans:
        covered = 0
        for insn in md.disasm(rom[start:end], start):
            ops = [operand(t) for t in _split_ops(insn.op_str)] if insn.op_str else []
            prog[insn.address] = (insn.mnemonic, ops, insn.address + insn.size)
            listing.append((insn.address, insn.bytes.hex(), insn.mnemonic, insn.op_str))
            covered += insn.size
        if covered != end - start:
            raise SystemExit(
                "loop_crossover_gate: capstone decoded %d of %d bytes in [$%06X,$%06X) "
                "— the extent is not a clean instruction run"
                % (covered, end - start, start, end))
    return prog, listing


# --------------------------------------------------------------------------
# The synthetic world
# --------------------------------------------------------------------------

SST = 0xFFB000          # synthetic player SST
BLOCK = 0xFFB100        # synthetic PlayerBlock
STACK = 0xFFB800        # a7
POISON = (0xDEAD0004, 0xDEAD0005, 0xDEAD0006, 0xDEAD0007)   # d4-d7


class World:
    """One player, one tile cache, one ROM image — carried across frames so the edge
    trigger's per-slot state persists exactly as it does in Player_Blocks."""

    def __init__(self, rom, prog, extents, syms, equs):
        self.rom = bytearray(rom)
        self.prog, self.extents, self.syms, self.k = prog, extents, syms, equs
        self.cpu = Cpu(bytes(self.rom), SST)
        self.cpu.RAM_LO = 0xFF0000
        for name, val in (("Cache_Left_Col", 0),
                          ("Cache_Head_Col", equs["TILE_CACHE_COLS"] - 1),
                          ("Cache_Top_Row", 0),
                          ("Cache_Bottom_Row", equs["TILE_CACHE_ROWS"] - 1),
                          ("Cache_Origin_Col", 0),
                          ("Cache_Origin_Row", 0)):
            self.cpu.write(syms[name] & 0xFFFFFF, val, "w")

    # --- the world's dials ------------------------------------------------
    def fill_plane(self, plane, attr):
        """Every cell of one collision plane gets the same attr byte. Filling the whole
        plane is deliberate: it means NO address arithmetic in this gate can agree with
        a bug in the routine's own cell derivation."""
        base = (self.syms["Tile_Cache_Collision"]
                + plane * self.k["TILE_CACHE_COLL_SIZE"]) & 0xFFFFFF
        for i in range(self.k["TILE_CACHE_COLL_SIZE"]):
            self.cpu.wb(base + i, attr)

    def set_crossover(self, attr, value):
        """Author a crossover by writing the ROM image — the ONE input the consumption
        experiment varies."""
        self.rom[self.syms["CrossoverTable"] + attr] = value
        self.cpu.rom = bytes(self.rom)

    def crossover_of(self, attr):
        return self.rom[self.syms["CrossoverTable"] + attr]

    def place(self, x, y, layer):
        self.cpu.write(SST + self.k["SST_x_pos"], (x & 0xFFFF) << 16, "l")
        self.cpu.write(SST + self.k["SST_y_pos"], (y & 0xFFFF) << 16, "l")
        self.cpu.wb(SST + self.k["SST_layer"], layer & 0xFF)

    def layer(self):
        return self.cpu.rb(SST + self.k["SST_layer"])

    # --- one frame --------------------------------------------------------
    def frame(self):
        cpu = self.cpu
        cpu.a[0], cpu.a[4], cpu.a[7] = SST, BLOCK, STACK
        for i, v in enumerate(POISON):
            cpu.d[4 + i] = v
        trace = Trace()
        execute(cpu, self.prog, self.syms[READ_SITE], self.extents, trace)
        if cpu.a[0] != SST:
            raise AssertionError("%s did not preserve a0 (RunObjects contract): "
                                 "$%08X" % (READ_SITE, cpu.a[0]))
        if cpu.a[4] != BLOCK:
            raise AssertionError("%s did not preserve a4 — Player_Main holds the "
                                 "slot's block there for the whole frame" % READ_SITE)
        if cpu.a[7] != STACK:
            raise AssertionError("%s returned with an unbalanced stack: $%08X"
                                 % (READ_SITE, cpu.a[7]))
        for i, v in enumerate(POISON):
            if cpu.d[4 + i] != v:
                raise AssertionError(
                    "%s clobbered d%d, which is outside its declared set — Player_Main "
                    "holds this frame's press bits in d6 across the call"
                    % (READ_SITE, 4 + i))
        return trace

    def layer_writes(self, trace):
        want = SST + self.k["SST_layer"]
        return [w for w in trace.writes if w[0] == want]


# --------------------------------------------------------------------------
# The sweeps
# --------------------------------------------------------------------------

# Two attr indices used as the cell's interned identity. Any non-zero value works —
# they only have to be different from each other and inside the 256-entry table.
ATTR_A, ATTR_B = 0x11, 0x22
IN_CELL = (200, 200)        # comfortably inside the synthetic cache window


def sweep_consumption(rom, prog, extents, syms, equs, fails):
    """THE experiment: hold everything fixed, vary one ROM byte.

    Runs the full cross product of {every legal crossover value} x {both layers}, each
    from a FRESH world, and grades the layer byte against the model. The XOVER_NONE row
    is the control and is also the shipped ROM's own state."""
    total = 0
    moved_by_rom = 0
    for value in (equs["XOVER_NONE"], equs["XOVER_TO_A"], equs["XOVER_TO_B"]):
        for layer in (equs["LAYER_PATH_A"], equs["LAYER_PATH_B"]):
            w = World(rom, prog, extents, syms, equs)
            w.fill_plane(0, ATTR_A)
            w.fill_plane(1, ATTR_A)
            if value != equs["XOVER_NONE"]:
                w.set_crossover(ATTR_A, value)
            shipped = rom[syms["CrossoverTable"] + ATTR_A]
            w.place(IN_CELL[0], IN_CELL[1], layer)
            trace = w.frame()
            got, want = w.layer(), model(layer, value, equs)
            total += 1
            if got != want:
                fails.append(("consumption", "CrossoverTable[$%02X]=%d layer=%d: layer "
                              "became %d, model says %d" % (ATTR_A, value, layer, got, want)))
            elif value != shipped and got != layer:
                moved_by_rom += 1
            # the mark must not fire from the wrong plane's fill either: both planes
            # carry ATTR_A here, so this row also pins that a plane-agnostic read would
            # not have been distinguishable — the plane sweep below is what separates them
    return total, moved_by_rom


def sweep_plane_select(rom, prog, extents, syms, equs, fails):
    """Anchor §3.3: the mark is read from the plane the player is ON. Plane A and plane
    B carry DIFFERENT attrs at the same cell, and the two attrs carry DIFFERENT marks,
    so a read that ignored the layer would land on the wrong one in half the cases."""
    total = 0
    for layer, expect_attr in ((equs["LAYER_PATH_A"], ATTR_A),
                               (equs["LAYER_PATH_B"], ATTR_B)):
        w = World(rom, prog, extents, syms, equs)
        w.fill_plane(0, ATTR_A)
        w.fill_plane(1, ATTR_B)
        # plane A's cell sends you to B, plane B's cell sends you to A: the §3.3 pair
        w.set_crossover(ATTR_A, equs["XOVER_TO_B"])
        w.set_crossover(ATTR_B, equs["XOVER_TO_A"])
        w.place(IN_CELL[0], IN_CELL[1], layer)
        w.frame()
        want = model(layer, w.crossover_of(expect_attr), equs)
        total += 1
        if w.layer() != want:
            fails.append(("plane-select",
                          "starting on layer %d the mark of the OTHER plane was used: "
                          "layer became %d, want %d" % (layer, w.layer(), want)))
    return total


def sweep_edge_trigger(rom, prog, extents, syms, equs, fails):
    """The four properties of the edge trigger, each with the case that would pass a
    weaker version of it."""
    total = 0
    SENTINEL = 0x5A

    def fresh(pair):
        w = World(rom, prog, extents, syms, equs)
        w.fill_plane(0, ATTR_A)
        w.fill_plane(1, ATTR_B if pair else ATTR_A)
        w.set_crossover(ATTR_A, equs["XOVER_TO_B"])
        if pair:
            w.set_crossover(ATTR_B, equs["XOVER_TO_A"])
        return w

    # (1) standing still does not re-fire. Weak triggers pass this too — it is here as
    #     the floor, not as the discriminator.
    w = fresh(False)
    w.place(*IN_CELL, layer=equs["LAYER_PATH_A"])
    w.frame()
    total += 1
    if w.layer() != equs["LAYER_PATH_B"]:
        fails.append(("edge", "the first frame in a marked cell did not fire"))
    w.cpu.wb(SST + equs["SST_layer"], SENTINEL)
    trace = w.frame()
    total += 1
    if w.layer_writes(trace):
        fails.append(("edge", "standing still in a marked cell WROTE the layer again"))

    # (2) THE DISCRIMINATOR — the §3.3 two-way pair. A trigger that re-arms on the
    #     layer change reads plane B's TO_A here on frame 2 and ping-pongs forever.
    w = fresh(True)
    w.place(*IN_CELL, layer=equs["LAYER_PATH_A"])
    w.frame()
    total += 1
    if w.layer() != equs["LAYER_PATH_B"]:
        fails.append(("edge", "the two-way pair's first crossing did not fire"))
    for frame in range(2, 6):
        trace = w.frame()
        total += 1
        if w.layer_writes(trace):
            fails.append(("edge", "the two-way pair PING-PONGED: frame %d wrote the "
                                  "layer again while the player had not moved" % frame))
            break

    # (3) sub-cell motion must not re-fire, at every offset inside one cell.
    for dx in range(equs["COLL_CELL_W"]):
        for dy in range(equs["COLL_CELL_H"]):
            if dx == 0 and dy == 0:
                continue
            w = fresh(True)
            base = (IN_CELL[0] & ~(equs["COLL_CELL_W"] - 1),
                    IN_CELL[1] & ~(equs["COLL_CELL_H"] - 1))
            w.place(base[0], base[1], equs["LAYER_PATH_A"])
            w.frame()
            w.cpu.wb(SST + equs["SST_layer"], SENTINEL)
            w.place(base[0] + dx, base[1] + dy, SENTINEL)
            trace = w.frame()
            total += 1
            if w.layer_writes(trace):
                fails.append(("edge", "moving +%d,+%d px — still inside one %dx%d cell "
                                      "— re-fired the crossover"
                              % (dx, dy, equs["COLL_CELL_W"], equs["COLL_CELL_H"])))

    # (4) ... and stepping into the NEXT cell on either axis must fire again. This is
    #     the half that stops (3) from being satisfiable by never firing at all.
    for name, dx, dy in (("+X", equs["COLL_CELL_W"], 0),
                         ("+Y", 0, equs["COLL_CELL_H"]),
                         ("-X", -equs["COLL_CELL_W"], 0),
                         ("-Y", 0, -equs["COLL_CELL_H"])):
        w = fresh(False)
        base = (IN_CELL[0] & ~(equs["COLL_CELL_W"] - 1),
                IN_CELL[1] & ~(equs["COLL_CELL_H"] - 1))
        w.place(base[0], base[1], equs["LAYER_PATH_A"])
        w.frame()
        w.cpu.wb(SST + equs["SST_layer"], equs["LAYER_PATH_A"])
        w.place(base[0] + dx, base[1] + dy, equs["LAYER_PATH_A"])
        trace = w.frame()
        total += 1
        if not w.layer_writes(trace):
            fails.append(("edge", "stepping one whole cell %s did NOT re-read the "
                                  "crossover" % name))
    return total


def sweep_off_cache(rom, prog, extents, syms, equs, fails):
    """A position outside the tile cache window returns CTYPE_AIR, which indexes
    CrossoverTable[0]. Index 0 is the attr set's reserved AIR entry
    (tools/collision_pipeline.py AttrSet.__init__), so it is XOVER_NONE by construction
    and nothing fires. Pinned here because it is the one path where the routine's input
    is not a real cell."""
    total = 0
    for x, y in ((0xF000, 200), (200, 0xF000)):
        w = World(rom, prog, extents, syms, equs)
        w.fill_plane(0, ATTR_A)
        w.set_crossover(ATTR_A, equs["XOVER_TO_B"])
        w.place(x, y, equs["LAYER_PATH_A"])
        trace = w.frame()
        total += 1
        if w.layer_writes(trace):
            fails.append(("off-cache", "a position outside the cache window ($%04X,"
                                       "$%04X) fired a crossover" % (x, y)))
    if rom[syms["CrossoverTable"] + equs["CTYPE_AIR"]] != equs["XOVER_NONE"]:
        fails.append(("off-cache", "CrossoverTable[CTYPE_AIR] is $%02X, not XOVER_NONE "
                                   "— the attr set's index 0 is supposed to be the "
                                   "reserved air entry"
                      % rom[syms["CrossoverTable"] + equs["CTYPE_AIR"]]))
    return total


def check_shipped_table(rom, syms, equs, notes, fails):
    """Two facts about the table the ROM actually ships, reported rather than asserted
    into a pass: the count of marked slots (zero today — that is WHY the sweeps above
    are synthetic) and the absence of the reserved value."""
    n = len(rom[syms["CrossoverTable"]:syms["CrossoverTable"] + 256])
    tbl = rom[syms["CrossoverTable"]:syms["CrossoverTable"] + 256]
    marked = sum(1 for b in tbl if b != equs["XOVER_NONE"])
    bad = [i for i, b in enumerate(tbl) if b == 3]
    notes.append("shipped CrossoverTable: %d slots, %d marked, %d holding the reserved "
                 "value 3" % (n, marked, len(bad)))
    if bad:
        fails.append(("shipped", "CrossoverTable holds the RESERVED value 3 at index "
                                 "%s — bake rule R1 is supposed to make that "
                                 "impossible" % bad[:8]))
    return marked


# --------------------------------------------------------------------------
# The committed cut
# --------------------------------------------------------------------------

CUT_NOTE = ("Player_LoopCrossover's and Collision_GetType's bytes, the shipped "
            "CrossoverTable, and the symbols/equates each shape was built with, per "
            "BUILD SHAPE. The two canonical shapes place these at different addresses, "
            "so one cut cannot serve both. Regenerate with "
            "tools/loop_crossover_gate.py --write-fixture (it preserves the other shape).")

CUT_KEYS = ("spans", "bytes", "table_addr", "table", "syms", "equs")


def shape_key(lst_path):
    return pathlib.Path(lst_path).name


def build_cut(rom, spans, syms, equs, lst_path, existing=None):
    doc = existing or {"_note": CUT_NOTE, "shapes": {}}
    doc["_note"] = CUT_NOTE
    doc.setdefault("shapes", {})[shape_key(lst_path)] = {
        "spans": [list(s) for s in spans],
        "bytes": [rom[a:b].hex() for a, b in spans],
        "table_addr": syms["CrossoverTable"],
        "table": rom[syms["CrossoverTable"]:syms["CrossoverTable"] + 256].hex(),
        "syms": {n: syms[n] for n in NEED_SYMS},
        "equs": {n: equs[n] for n in NEED_EQUS},
    }
    return doc


def _read_cut_doc(path):
    doc = json.loads(pathlib.Path(path).read_text())
    if "shapes" not in doc:
        raise SystemExit("loop_crossover_gate: %s predates the shape-keyed format; "
                         "regenerate it with --write-fixture" % path)
    return doc


def cut_shapes(path):
    return sorted(_read_cut_doc(path)["shapes"])


def load_cut(path, shape=None):
    """Rebuild a sparse ROM image + this gate's inputs from one shape's committed cut."""
    doc = _read_cut_doc(path)
    if shape is None:
        shape = sorted(doc["shapes"])[0]
    cut = doc["shapes"][shape]
    missing = [k for k in CUT_KEYS if k not in cut]
    if missing:
        raise SystemExit(
            "loop_crossover_gate: %s shape %r is missing %s — it was stamped by an "
            "older version of this gate and cannot be graded. Regenerate with "
            "tools/loop_crossover_gate.py --write-fixture." % (path, shape, ", ".join(missing)))
    spans = [tuple(s) for s in cut["spans"]]
    top = max(max(b for _, b in spans), cut["table_addr"] + 256)
    rom = bytearray(top)
    for (a, b), hx in zip(spans, cut["bytes"]):
        rom[a:b] = bytes.fromhex(hx)
    rom[cut["table_addr"]:cut["table_addr"] + 256] = bytes.fromhex(cut["table"])
    return bytes(rom), spans, cut["syms"], cut["equs"]


def check_cut(rom, spans, syms, equs, path, lst_path):
    """THIS SHAPE's committed cut must still be the same CODE and the same DATA the
    fresh ROM holds — up to relocation, and nothing more than relocation.

    This used to compare the spans' absolute addresses and then the spans' raw bytes.
    Both are relocation-sensitive and this subject is the worst case for it: the read
    site calls `jsr Collision_GetType` with an absolute-SHORT operand, and
    Collision_GetType is fourteen `move.w Cache_*.w` / `lea SolidityTable.l` operands
    deep, so a level content change that moves either one rewrites the other's bytes.
    The old check called that "the ROUTINE changed", which was a fabricated reason: the
    routine had not changed at all. See the normalisation note in sprite_tilt_gate.py.

    Still proved: the decoded instruction stream of both routines, the shipped
    CrossoverTable's bytes, the existence of every anchored symbol, and (new) that the
    EQUATES the pytest lane models against are the ones this build was assembled with.
    No longer required: that any of it sits at the address it did when stamped.
    """
    doc = _read_cut_doc(path)
    shape = shape_key(lst_path)
    if shape not in doc["shapes"]:
        raise SystemExit(
            "loop_crossover_gate: %s carries no cut for shape %r (have: %s) — the "
            "pytest lane covers the other shape(s) only. Regenerate with "
            "--write-fixture." % (path, shape, ", ".join(sorted(doc["shapes"]))))
    cut = doc["shapes"][shape]
    problems = []

    gone = [n for n in NEED_SYMS if n not in syms]
    if gone:
        problems.append("symbol(s) the cut anchors are GONE from the listing: %s — "
                        "renamed or removed, not moved" % ", ".join(gone))

    cut_names = {a: n for n, a in cut["syms"].items()}
    live_names = {syms[n]: n for n in cut["syms"] if n in syms}
    for i, (name, (a, b), hx) in enumerate(
            zip((READ_SITE, LOOKUP), spans, cut["bytes"])):
        cb = bytes.fromhex(hx)
        ca, cbend = cut["spans"][i][0], cut["spans"][i][0] + len(cb)
        if len(cb) != b - a:
            problems.append("%s: the routine's LENGTH changed (cut %d B, live %d B) — "
                            "it was edited, not moved" % (name, len(cb), b - a))
            continue
        img = bytearray(cbend)
        img[ca:cbend] = cb
        cut_rows, cut_unres = normalize_stream(bytes(img), ca, cbend, cut_names,
                                               "loop_crossover_gate")
        live_rows, live_unres = normalize_stream(rom, a, b, live_names,
                                                 "loop_crossover_gate")
        d = stream_diff(cut_rows, live_rows, name)
        if d:
            problems += d + unresolved_note(name, cut_unres + live_unres)

    if "CrossoverTable" in syms:
        shipped = rom[syms["CrossoverTable"]:syms["CrossoverTable"] + 256].hex()
        if shipped != cut["table"]:
            problems.append(
                "the shipped CrossoverTable's BYTES changed (its address is allowed to "
                "move and was not compared). That is the FIRST authored crossover "
                "reaching the ROM, which is a thing to celebrate and then re-stamp "
                "deliberately: the pytest lane's control row ('the unmodified ROM must "
                "not move the layer') is graded against this blob.")

    drift = ["%s: cut %s, build %s" % (n, cut["equs"][n], equs[n])
             for n in sorted(cut["equs"]) if n in equs and equs[n] != cut["equs"][n]]
    if drift:
        problems.append("equate(s) the pytest lane models against changed — the lane "
                        "would grade this build against the OLD geometry: %s"
                        % "; ".join(drift))

    if problems:
        raise SystemExit(
            "loop_crossover_gate: %s shape %r is STALE — the pytest lane is grading "
            "code or constants this build does not have:\n  %s\n  Regenerate with "
            "tools/loop_crossover_gate.py --write-fixture."
            % (path, shape, "\n  ".join(problems)))


# --------------------------------------------------------------------------

def run_all(rom, prog, extents, syms, equs):
    fails, notes = [], []
    marked = check_shipped_table(rom, syms, equs, notes, fails)
    n1, moved = sweep_consumption(rom, prog, extents, syms, equs, fails)
    n2 = sweep_plane_select(rom, prog, extents, syms, equs, fails)
    n3 = sweep_edge_trigger(rom, prog, extents, syms, equs, fails)
    n4 = sweep_off_cache(rom, prog, extents, syms, equs, fails)
    if moved == 0:
        fails.append(("consumption", "NOT ONE execution changed the layer because of a "
                                     "ROM byte this gate authored. Either the read site "
                                     "never fires, or this gate is not varying what it "
                                     "thinks it is — an all-green run with moved=0 is "
                                     "the vacuous result this file exists to refuse."))
    return {"executions": n1 + n2 + n3 + n4, "consumption": n1, "plane": n2,
            "edge": n3, "off_cache": n4, "moved_by_rom": moved, "marked": marked,
            "fails": fails, "notes": notes}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lst", required=True)
    ap.add_argument("--rom", required=True)
    ap.add_argument("--fixture",
                    default=str(TOOLS / "fixtures" / "loop_crossover_cut.json"))
    ap.add_argument("--write-fixture", action="store_true")
    ap.add_argument("--built-after", type=int, default=None,
                    help="unix ts; both artifacts must be newer (staleness guard)")
    ap.add_argument("--gate", action="store_true", help="exit 1 on any failure")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if args.built_after is not None:
        for p in (pathlib.Path(args.rom), pathlib.Path(args.lst)):
            age = int(p.stat().st_mtime) - args.built_after
            if age < 0:
                print("loop_crossover_gate: %s is OLDER than this build started (%ds) "
                      "— refusing to grade a stale artifact" % (p, -age))
                return 1

    rom = pathlib.Path(args.rom).read_bytes()
    syms, equs = parse_lst(args.lst)
    spans = [routine_extent(syms, READ_SITE), routine_extent(syms, LOOKUP)]
    prog, listing = decode(rom, spans)
    extents = [tuple(s) for s in spans]

    if args.verbose:
        for (a, b) in spans:
            print("  $%06X..$%06X (%d bytes)" % (a, b, b - a))
        for a, byt, m, o in listing:
            print("    %06X  %-14s %s %s" % (a, byt, m, o))

    if args.write_fixture:
        p = pathlib.Path(args.fixture)
        p.parent.mkdir(parents=True, exist_ok=True)
        existing = _read_cut_doc(p) if p.exists() else None
        doc = build_cut(rom, spans, syms, equs, args.lst, existing)
        p.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        print("loop_crossover_gate: wrote %s (shapes: %s)"
              % (p, ", ".join(sorted(doc["shapes"]))))
        return 0

    r = run_all(rom, prog, extents, syms, equs)

    print("loop_crossover_gate [%s]:" % args.lst)
    print("  %s $%06X-$%06X (%d B) + %s $%06X-$%06X (%d B), both EXECUTED"
          % (READ_SITE, spans[0][0], spans[0][1] - 1, spans[0][1] - spans[0][0],
             LOOKUP, spans[1][0], spans[1][1] - 1, spans[1][1] - spans[1][0]))
    for n in r["notes"]:
        print("  %s" % n)
    print("  %d executions: %d consumption, %d plane-select, %d edge-trigger, "
          "%d off-cache" % (r["executions"], r["consumption"], r["plane"],
                            r["edge"], r["off_cache"]))
    print("  %d of them changed Sst.layer BECAUSE a byte of CrossoverTable in the ROM "
          "image was changed and nothing else was — that is the consumption claim, and "
          "the unmodified table is its control" % r["moved_by_rom"])

    if r["fails"]:
        print("  FAIL — %d finding(s):" % len(r["fails"]))
        for kind, why in r["fails"][:20]:
            print("    [%s] %s" % (kind, why))
        if len(r["fails"]) > 20:
            print("    ... and %d more" % (len(r["fails"]) - 20))

    if pathlib.Path(args.fixture).exists():
        try:
            check_cut(rom, spans, syms, equs, args.fixture, args.lst)
        except SystemExit as e:
            print("  %s" % e)
            return 1 if args.gate else 0
        print("  fixture: %s [%s] — both routines' decoded instruction streams "
              "identical (relocation normalised), CrossoverTable byte-identical, "
              "%d equates match"
              % (pathlib.Path(args.fixture).name, shape_key(args.lst), len(NEED_EQUS)))
    else:
        print("  fixture: %s MISSING — the pytest lane has nothing to grade "
              "(--write-fixture)" % args.fixture)
        if args.gate:
            return 1

    if r["fails"]:
        return 1 if args.gate else 0
    print("  OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
