#!/usr/bin/env python3
"""layer_line_gate.py — execute the built ROM's Player_LayerLines against Sonic 2's Obj03 rule.

WHY THIS SHAPE. Player_LayerLines (games/sonic4/player/player_common.emp, S2CLIP-PLANE-SWITCH)
is in every sonic4 ROM, and in every CANONICAL one it never runs: OJZ binds no layer-line
table, so Player_Main's null test skips it on every frame. A correct routine and a broken one
therefore build the identical canonical ROM and play identically there, and no gate over
canonical content can tell them apart (the same vacuity tools/loop_crossover_gate.py was built
around). The clip act runs it, but only in an off-canonical shape and only along the paths a
drive happens to take (tools/s2clip_layer_line_witness.py). So the subject here is the
ROUTINE, taken from THIS build as bytes, executed against synthetic tables that exercise every
form a table can hold, frame by frame, beside an independent model of Sonic 2's Obj03:

    .lst          ->  Player_LayerLines' extent, and the SST_*, LL_*, ST_IN_AIR, LAYER_PATH_*,
                      PHYS_GSP_CAP equates the build was assembled with
    .bin          ->  the routine's bytes (and, in a clip ROM, the shipped table itself)
    capstone      ->  an independent decoder
    this file     ->  a strict executor for exactly the forms the routine decodes to (anything
                      else raises, so a new addressing mode stops the gate, never passes it)
    the model     ->  Obj03 (s2.asm `Obj03:` MainX/MainY and their _Alt halves), with ONE flag
                      per line per player, which is what the routine claims to reproduce with
                      one remembered position per player

THE MODEL, stated so a reader can check it against s2.asm without reading the executor. Each
row is a line with its own side flag. A vertical row's side is `x >= key`, a horizontal
row's `y >= ll_a`. Every frame the player moved by at most the physics cap on both axes, each
row (in table order) whose side changed FIRES if the other coordinate is inside [lo, hi) and
the row is not grounded-only while ST_IN_AIR is set; firing sets the layer (unless LL_KEEP_PATH)
to B or A from the crossing direction's bit, clears art_tile bit 15 and sets it again if that
direction's priority bit is set. The side flips whether or not it fires. A step longer than
the cap on either axis crosses nothing and re-seeds every side (the routine's documented
stand-in for Obj03's load window). THE WINDOW IS NOT IN THE MODEL: the model looks at every
row every frame. That is the point: the routine's cursor-and-window scan must lose nothing the
full scan would fire.

WHAT IS COMPARED, per frame: Sst.layer, the whole art_tile word (only bit 15 may ever move),
and the WRITE SET (only layer, art_tile and the two PlayerBlock longs may be written). And it
refuses a run in which any form of firing never happened: a vertical line each way, a
horizontal segment each way, a grounded-only line skipped in the air, a priority-only line, a
priority raised and a priority cleared. An all-agree run that never fired is the vacuous
result this file exists to refuse.

THE COST NOTE is produced here too (--cost), from the same executions: MC68000UM cycle counts
for every instruction actually run, summed per frame. It is the 68000's own timing, not bus
contention, so every figure is a floor, the same basis as tools/loop_crossover_cost.py.

EXIT: 0 agree + non-vacuous, 1 a disagreement (or a vacuous run), 2 COULD NOT RUN (stale or
missing artifacts, a symbol or equate absent, a form the executor does not model).

Usage:
    tools/layer_line_gate.py --rom s4.debug.bin --lst s4.debug.lst [--built-after T0] [--cost]
    tools/layer_line_gate.py --rom s4.s2clip.debug.bin --lst s4.s2clip.debug.lst \\
        --cost --trajectory drive.json     # per-frame cost of a real drive over the real table
"""
import argparse
import json
import pathlib
import random
import re
import sys

TOOLS = pathlib.Path(__file__).resolve().parent
REPO = TOOLS.parent
sys.path.insert(0, str(TOOLS))

import artifact_provenance                               # noqa: E402
import loop_crossover_gate as lxg                        # noqa: E402
import region_table                                      # noqa: E402
from sprite_tilt_gate import UnsupportedInstruction      # noqa: E402

SUBJECT = "Player_LayerLines"
CALLER = "Player_Main"
TABLE_SYM = "OJZ_Clip_LayerLines"
NEED_EQUS = ("SST_x_pos", "SST_y_pos", "SST_layer", "SST_status", "SST_art_tile",
             "LL_KEEP_PATH", "LL_GROUNDED", "LL_HORIZONTAL", "LL_FWD_B", "LL_BACK_B",
             "LL_FWD_HI", "LL_BACK_HI", "LL_SEG_W", "LL_KEY_BEFORE", "LL_KEY_AFTER",
             "ST_IN_AIR", "LAYER_PATH_A", "LAYER_PATH_B", "PHYS_GSP_CAP")

SST = 0xFFB000
BLOCK = 0xFFB100
TABLE = 0xFF4000            # a synthetic table lives in work RAM; the cursor is a pointer
POISON = {6: 0xDEAD0006, 7: 0xDEAD0007}   # d6 (the press bits) and d7 must survive
ART_PRIO = 0x8000


#: The model's counters that mean "a line's side changed inside its extent" (a crossing
#: the routine had to find), as opposed to the discontinuity counter.
FIRE_KINDS = ("Vfwd", "Vback", "Hfwd", "Hback")


class CouldNotRun(Exception):
    pass


# ---------------------------------------------------------------------------
# Listing, layout, decode
# ---------------------------------------------------------------------------

def parse_lst(path):
    syms, equs = {}, {}
    for line in pathlib.Path(path).read_text(errors="replace").splitlines():
        m = lxg._SYM.match(line)
        if m:
            syms.setdefault(m.group(1), int(m.group(2), 16))
            continue
        m = lxg._EQU.match(line)
        if m:
            equs.setdefault(m.group(1), int(m.group(2), 16))
    missing = [n for n in (SUBJECT, CALLER) if n not in syms] + \
              [n for n in NEED_EQUS if n not in equs]
    if missing:
        raise CouldNotRun("%s lacks %s" % (path, ", ".join(missing)))
    return syms, equs


_TYPE_BYTES = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4}


def player_block_layout(path=REPO / "games" / "sonic4" / "config" / "ram.emp"):
    """PlayerBlock's field offsets, accumulated from its declared types. Not through
    region_table.struct_layout: that reader checks the FIRST `$` in every comment as an offset,
    and PlayerBlock's comments quote formulas like `(angle+$20)>>6`."""
    text = pathlib.Path(path).read_text()
    m = re.search(r"^pub struct PlayerBlock\s*\{(.*?)^\}", text, re.M | re.S)
    if not m:
        raise CouldNotRun("games/sonic4/config/ram.emp has no `pub struct PlayerBlock`")
    off, out = 0, {}
    for raw in m.group(1).splitlines():
        fm = re.match(r"\s*(\w+)\s*:\s*(\w+)\s*,", raw.split("//")[0])
        if not fm:
            continue
        if fm.group(2) not in _TYPE_BYTES:
            raise CouldNotRun("PlayerBlock.%s has type %s, which this reader does not size"
                              % (fm.group(1), fm.group(2)))
        out[fm.group(1)] = off
        off += _TYPE_BYTES[fm.group(2)]
    return out


def layouts():
    """PlayerBlock and LayerLine field offsets, out of the .emp declarations (LayerLine through
    tools/region_table.struct_layout, which checks its `// $HH` comments against its types)."""
    blk = player_block_layout()
    row, size = region_table.struct_layout("LayerLine")
    for f in ("ll_prev", "ll_cursor"):
        if f not in blk:
            raise CouldNotRun("PlayerBlock has no %s" % f)
    return blk, row, size


def extent(syms, name):
    """[start, end): end is the next GLOBAL symbol above start. Every `$`-prefixed name is a
    hygienic local (a proc's `.label` or an asm template's), and phased symbols carry a bank
    VMA, not a ROM address (lxg.vma_phased_symbol_names)."""
    start = syms[name]
    phased = lxg.vma_phased_symbol_names()
    above = [a for n, a in syms.items() if a > start and not n.startswith("$")
             and n not in phased]
    if not above:
        raise CouldNotRun("nothing follows %s in the listing" % name)
    return start, min(above)


def decode(rom, span):
    """{pc: (mnemonic, ops, next, raw_op_str, size)} over one routine. Keeps capstone's raw
    operand text: `(a1)` and `$0(a1)` are different modes with different timings, and the
    shared operand grammar folds them together."""
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_M68K,
                     capstone.CS_MODE_BIG_ENDIAN | capstone.CS_MODE_M68K_000)
    prog, covered = {}, 0
    for insn in md.disasm(rom[span[0]:span[1]], span[0]):
        ops = [lxg.operand(t) for t in lxg._split_ops(insn.op_str)] if insn.op_str else []
        prog[insn.address] = (insn.mnemonic, ops, insn.address + insn.size, insn.op_str,
                              insn.size)
        covered += insn.size
    if covered != span[1] - span[0]:
        raise CouldNotRun("capstone decoded %d of %d bytes of %s"
                          % (covered, span[1] - span[0], SUBJECT))
    return prog


# ---------------------------------------------------------------------------
# The executor and its cycle table (MC68000UM section 8, no wait states)
# ---------------------------------------------------------------------------

_EA_BW = {"d": 0, "a": 0, "ind": 4, "disp": 8, "imm": 4, "absw": 8, "absl": 12}
_EA_L = {"d": 0, "a": 0, "ind": 8, "disp": 12, "imm": 8, "absw": 12, "absl": 16}


def _mode(op, raw):
    if op[0] == "disp" and op[1] == 0 and re.fullmatch(r"\(a[0-7]\)", raw.strip()):
        return "ind"
    return op[0]


def cycles(mnem, ops, raws, size, taken):
    base = mnem.split(".")[0]
    sz = mnem.split(".")[1] if "." in mnem else "w"
    modes = [_mode(o, r) for o, r in zip(ops, raws)]
    ea = _EA_L if sz == "l" else _EA_BW

    def move_dst(m):
        return {"d": 0, "a": 0, "ind": 4 if sz != "l" else 8, "disp": 8 if sz != "l" else 12,
                "absw": 8 if sz != "l" else 12, "absl": 12 if sz != "l" else 16}[m]
    if base == "rts":
        return 16
    if base in ("swap",):
        return 4
    if base == "exg":
        return 6
    if base == "bra":
        return 10
    if base in lxg.BRANCHES:
        return 10 if taken else (8 if size == 2 else 12)
    if base in ("move", "movea"):
        return 4 + ea[modes[0]] + move_dst(modes[1])
    if base in ("cmp", "sub", "add") and modes[1] == "d":
        if sz == "l":
            return (6 if base == "cmp" else 8) if modes[0] in ("d", "a", "imm") \
                else 6 + ea[modes[0]]
        return 4 + ea[modes[0]]
    if base in ("cmpi", "addi", "subi") and modes[1] == "d":
        return (14 if base == "cmpi" else 16) if sz == "l" else 8
    if base in ("addq", "subq"):
        if modes[1] == "a":
            return 8
        if modes[1] == "d":
            return 8 if sz == "l" else 4
    if base in ("andi", "ori") and modes[1] in ("ind", "disp", "absw", "absl"):
        return (20 if sz == "l" else 12) + ea[modes[1]]
    if base == "btst" and modes[0] == "imm":
        return 10 if modes[1] == "d" else 8 + _EA_BW[modes[1]]
    if base == "tst":
        return 4 + ea[modes[0]]
    if base in ("bsr", "jsr"):
        return 18
    raise UnsupportedInstruction("no timing for %s %s" % (mnem, ", ".join(raws)))


class Cpu(lxg.Cpu):
    pass


def execute(cpu, prog, entry, span, trace, limit=4000):
    """Run from `entry` to its rts. Records every write and every executed instruction's
    cycles in `trace`."""
    pc = entry
    steps = 0
    while True:
        steps += 1
        if steps > limit:
            raise UnsupportedInstruction("instruction limit — %s did not return" % SUBJECT)
        if pc not in prog:
            raise UnsupportedInstruction("execution left %s at $%06X" % (SUBJECT, pc))
        mnem, ops, nxt, raw, isize = prog[pc]
        raws = lxg._split_ops(raw) if raw else []
        base = mnem.split(".")[0]
        size = mnem.split(".")[1] if "." in mnem else "w"
        lxg._sized(cpu, size)
        if base == "rts":
            trace["cycles"] += cycles(mnem, ops, raws, isize, False)
            return
        if base in lxg.BRANCHES:
            cc = "ra" if base == "bra" else base[1:]
            hit = cpu.cond(cc)
            trace["cycles"] += cycles(mnem, ops, raws, isize, hit)
            pc = ops[0][1] if hit else nxt
            continue
        trace["cycles"] += cycles(mnem, ops, raws, isize, None)
        if base in ("move", "movea"):
            v = cpu.src(ops[0], size)
            if base == "move":
                cpu.logic_flags(v, size)
            if ops[1][0] in ("disp", "idx", "absw", "absl"):
                trace["writes"].append((cpu.ea_addr(ops[1]), size))
            cpu.dst_write(ops[1], v, size)
        elif base == "swap":
            r = ops[0][1]
            v = cpu.d[r] & 0xFFFFFFFF
            v = ((v >> 16) | (v << 16)) & 0xFFFFFFFF
            cpu.d[r] = v
            cpu.logic_flags(v, "l")
        elif base == "exg":
            (k0, r0), (k1, r1) = ops[0][:2], ops[1][:2]
            bank = {"d": cpu.d, "a": cpu.a}
            bank[k0][r0], bank[k1][r1] = bank[k1][r1], bank[k0][r0]
        elif base in ("cmp", "cmpi"):
            cpu.sub_flags(cpu.src(ops[1], size), cpu.src(ops[0], size), size)
        elif base in ("add", "addi", "addq", "sub", "subi", "subq"):
            b, a = cpu.src(ops[0], size), cpu.src(ops[1], size)
            if ops[1][0] == "a":        # address register: whole register, no flags
                v = cpu.a[ops[1][1]]
                cpu.a[ops[1][1]] = (v + b if base.startswith("add") else v - b) & 0xFFFFFFFF
            else:
                r = (cpu.add_flags if base.startswith("add") else cpu.sub_flags)(a, b, size)
                if ops[1][0] in ("disp", "idx", "absw", "absl"):
                    trace["writes"].append((cpu.ea_addr(ops[1]), size))
                cpu.dst_write(ops[1], r, size)
        elif base in ("andi", "ori"):
            a, b = cpu.src(ops[1], size), cpu.src(ops[0], size)
            r = a & b if base == "andi" else a | b
            cpu.logic_flags(r, size)
            if ops[1][0] in ("disp", "idx", "absw", "absl"):
                trace["writes"].append((cpu.ea_addr(ops[1]), size))
            cpu.dst_write(ops[1], r, size)
        elif base == "btst":
            bit = ops[0][1]
            if ops[1][0] == "d":
                cpu.z = not (cpu.d[ops[1][1]] >> (bit & 31)) & 1
            else:
                cpu.z = not (cpu.read(cpu.ea_addr(ops[1]), "b") >> (bit & 7)) & 1
        elif base == "tst":
            cpu.logic_flags(cpu.src(ops[0], size), size)
        else:
            raise UnsupportedInstruction("instruction not modelled: %s %s" % (mnem, raw))
        pc = nxt


# ---------------------------------------------------------------------------
# The model: Obj03 with one side flag per line
# ---------------------------------------------------------------------------

class Obj03Model:
    def __init__(self, rows, k, step_max):
        self.rows, self.k, self.step = rows, k, step_max
        self.side = None

    def _sides(self, x, y):
        h = 1 << self.k["LL_HORIZONTAL"]
        return [(y >= r[1]) if r[3] & h else (x >= r[0]) for r in self.rows]

    def seed(self, x, y):
        self.side = self._sides(x, y)
        self.at = (x, y)

    def frame(self, x, y, in_air, layer, art, kinds):
        k, h = self.k, 1 << self.k["LL_HORIZONTAL"]
        px, py = self.at
        self.at = (x, y)
        if (x, y) == (px, py):
            return layer, art
        if abs(x - px) > self.step or abs(y - py) > self.step:
            self.side = self._sides(x, y)
            kinds["discontinuity"] += 1
            return layer, art
        now = self._sides(x, y)
        for i, r in enumerate(self.rows):
            if now[i] == self.side[i]:
                continue
            fwd = now[i]
            self.side[i] = now[i]
            key, a, b, f = r
            horiz = bool(f & h)
            lo, hi, other = (key, b, x) if horiz else (a, b, y)
            if not (lo <= other < hi):
                continue
            kinds[("H" if horiz else "V") + ("fwd" if fwd else "back")] += 1
            if f & (1 << k["LL_GROUNDED"]) and in_air:
                kinds["grounded_skip"] += 1
                continue
            if f & (1 << k["LL_KEEP_PATH"]):
                kinds["keep_path"] += 1
            else:
                bit = k["LL_FWD_B"] if fwd else k["LL_BACK_B"]
                layer = k["LAYER_PATH_B"] if f & (1 << bit) else k["LAYER_PATH_A"]
            hib = k["LL_FWD_HI"] if fwd else k["LL_BACK_HI"]
            kinds["prio_clear"] += bool(art & ART_PRIO)
            art &= ~ART_PRIO & 0xFFFF
            if f & (1 << hib):
                art |= ART_PRIO
                kinds["prio_set"] += 1
        return layer, art


# ---------------------------------------------------------------------------
# The synthetic tables and walks
# ---------------------------------------------------------------------------

def synthetic_table(rng, k, x0, x1, y0, y1, n_v, n_h):
    """Rows (key, a, b, flags) sorted by key, stable: V lines anywhere in the box, H lines
    cut into LL_SEG_W segments sharing one flag byte, and every flag combination the table
    rules allow (a priority-only row names no path)."""
    seg, h = k["LL_SEG_W"], 1 << k["LL_HORIZONTAL"]
    keep, fb, bb = (1 << k["LL_KEEP_PATH"]), (1 << k["LL_FWD_B"]), (1 << k["LL_BACK_B"])
    others = [(1 << k[n]) for n in ("LL_GROUNDED", "LL_FWD_HI", "LL_BACK_HI")]

    def flags():
        f = 0
        for bit in others:
            if rng.random() < 0.4:
                f |= bit
        if rng.random() < 0.2:
            f |= keep
        else:
            f |= fb if rng.random() < 0.5 else 0
            f |= bb if rng.random() < 0.5 else 0
        return f
    rows = []
    for _ in range(n_v):
        x = rng.randrange(x0, x1)
        c = rng.randrange(y0, y1)
        half = rng.choice((16, 32, 64, 128))
        rows.append((x, c - half, c + half, flags()))
    for _ in range(n_h):
        y = rng.randrange(y0, y1)
        c = rng.randrange(x0, x1)
        half = rng.choice((16, 32, 64, 128))
        f = flags() | h
        x = c - half
        while x < c + half:
            e = min(x + seg, c + half)
            rows.append((x, y, e, f))
            x = e
    return sorted(rows, key=lambda r: r[0])     # stable: equal keys keep insertion order


def walk(rng, x0, x1, y0, y1, n, step):
    x, y = rng.randrange(x0, x1), rng.randrange(y0, y1)
    out = [(x, y, False)]
    air = False
    for _ in range(n):
        r = rng.random()
        if r < 0.03:
            x, y = rng.randrange(x0, x1), rng.randrange(y0, y1)      # a teleport
        elif r < 0.08:
            pass                                                      # standing still
        elif r < 0.12:
            x += rng.choice((-step, step, -step - 1, step + 1))       # both sides of the bound
        else:
            x += rng.randint(-step, step)
            y += rng.randint(-step, step)
        x, y = max(x0 - 200, min(x1 + 200, x)), max(y0 - 200, min(y1 + 200, y))
        if rng.random() < 0.1:
            air = not air
        out.append((x, y, air))
    return out


# ---------------------------------------------------------------------------
# Running the routine
# ---------------------------------------------------------------------------

class Runner:
    def __init__(self, rom, prog, span, equs, blk, row, row_size):
        self.rom, self.prog, self.span, self.e = rom, prog, span, equs
        self.blk, self.row, self.row_size = blk, row, row_size

    def fresh(self, table_addr, rows_in_ram, x, y, layer, art, status):
        cpu = Cpu(self.rom, SST)
        cpu.a[0], cpu.a[4], cpu.a[7] = SST, BLOCK, 0xFFB800
        for r, v in POISON.items():
            cpu.d[r] = v
        if rows_in_ram is not None:
            k = self.e
            full = [(k["LL_KEY_BEFORE"], 0, 0, 0)] + rows_in_ram + [(k["LL_KEY_AFTER"], 0, 0, 0)]
            for i, (key, a, b, f) in enumerate(full):
                base = table_addr + i * self.row_size
                cpu.write(base + self.row["ll_key"], key, "w")
                cpu.write(base + self.row["ll_a"], a, "w")
                cpu.write(base + self.row["ll_b"], b, "w")
                cpu.write(base + self.row["ll_flags"], f, "b")
        cpu.write(BLOCK + self.blk["ll_cursor"], table_addr, "l")
        cpu.write(BLOCK + self.blk["ll_prev"], ((x & 0xFFFF) << 16) | (y & 0xFFFF), "l")
        self.place(cpu, x, y, layer, art, status)
        return cpu

    def place(self, cpu, x, y, layer, art, status):
        cpu.write(SST + self.e["SST_x_pos"], ((x & 0xFFFF) << 16) | 0x1234, "l")
        cpu.write(SST + self.e["SST_y_pos"], ((y & 0xFFFF) << 16) | 0x5678, "l")
        cpu.write(SST + self.e["SST_layer"], layer, "b")
        cpu.write(SST + self.e["SST_art_tile"], art, "w")
        cpu.write(SST + self.e["SST_status"], status, "b")

    def frame(self, cpu):
        trace = {"cycles": 0, "writes": []}
        execute(cpu, self.prog, self.span[0], self.span, trace)
        allowed = {(SST + self.e["SST_layer"], "b"), (SST + self.e["SST_art_tile"], "w"),
                   (BLOCK + self.blk["ll_prev"], "l"), (BLOCK + self.blk["ll_cursor"], "l")}
        stray = [w for w in trace["writes"] if w not in allowed]
        for r, v in POISON.items():
            if cpu.d[r] != v:
                stray.append(("d%d clobbered" % r, cpu.d[r]))
        if cpu.a[0] != SST or cpu.a[4] != BLOCK:
            stray.append(("a0/a4 not preserved", cpu.a[0], cpu.a[4]))
        return trace, stray

    def layer_art(self, cpu):
        return (cpu.read(SST + self.e["SST_layer"], "b"),
                cpu.read(SST + self.e["SST_art_tile"], "w"))


def run_walks(runner, e, seed, n_tables, n_steps, fails, kinds, costs, rows_override=None,
              table_addr=TABLE, box=(1000, 1800, 1000, 1500)):
    step = e["PHYS_GSP_CAP"] >> 8
    in_air_bit = 1 << e["ST_IN_AIR"]
    x0, x1, y0, y1 = box
    for t in range(n_tables):
        rng = random.Random(seed * 1000 + t)
        rows = rows_override if rows_override is not None else \
            synthetic_table(rng, e, x0, x1, y0, y1, rng.randint(3, 25), rng.randint(0, 8))
        path = walk(rng, x0, x1, y0, y1, n_steps, step)
        layer, art = rng.choice((0, 1)), rng.randrange(0, 0x10000)
        x, y, air = path[0]
        cpu = runner.fresh(table_addr, None if rows_override is not None else rows,
                           x, y, layer, art, in_air_bit if air else 0)
        model = Obj03Model(rows, e, step)
        model.seed(x, y)
        for f, (x, y, air) in enumerate(path[1:], 1):
            status = (in_air_bit if air else 0) | (rng.randrange(0, 256) & ~in_air_bit)
            runner.place(cpu, x, y, layer, art, status)
            before = dict(kinds)
            prev_at = model.at
            layer, art = model.frame(x, y, air, layer, art, kinds)
            if (x, y) == prev_at:
                klass = "idle"
            elif kinds["discontinuity"] != before["discontinuity"]:
                klass = "discontinuity"
            elif any(kinds[n] != before[n] for n in FIRE_KINDS):
                klass = "crossed"
            else:
                klass = "quiet"
            trace, stray = runner.frame(cpu)
            costs.append((trace["cycles"], klass, (x, y)))
            got = runner.layer_art(cpu)
            if got != (layer, art) or stray:
                fails.append("table %d frame %d at (%d, %d)%s: routine layer %d art $%04X, "
                             "model layer %d art $%04X%s"
                             % (t, f, x, y, " airborne" if air else "", got[0], got[1],
                                layer, art, (", stray " + repr(stray)) if stray else ""))
                layer, art = got           # keep going from the routine's state
                if len(fails) > 20:
                    return


def caller_early_out(rom, syms, blk):
    """The three instructions Player_Main runs for this check, read out of the ROM, and what
    they cost: (null-table cycles, table-present overhead excluding the routine)."""
    span = extent(syms, CALLER)
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_M68K,
                     capstone.CS_MODE_BIG_ENDIAN | capstone.CS_MODE_M68K_000)
    insns = list(md.disasm(rom[span[0]:span[1]], span[0]))
    want = "$%x(a4)" % blk["ll_cursor"]
    for i, ins in enumerate(insns):
        if ins.mnemonic == "tst.l" and ins.op_str.replace(" ", "") == want:
            beq, call = insns[i + 1], insns[i + 2]
            tgt = syms[SUBJECT]
            if beq.mnemonic.split(".")[0] != "beq" or call.mnemonic.split(".")[0] not in ("bsr", "jsr") \
                    or int(call.op_str.lstrip("$").split(".")[0], 16) & 0xFFFFFF != tgt:
                raise CouldNotRun("Player_Main's tst.l %s is not followed by beq + a call to %s"
                                  % (want, SUBJECT))
            tst = 16
            return (tst + 10, tst + (8 if beq.size == 2 else 12) + 18)
    raise CouldNotRun("Player_Main has no `tst.l %s`: the per-frame null test is gone" % want)


def shipped_rows(rom, syms, e, row, row_size):
    if TABLE_SYM not in syms:
        return None
    base = syms[TABLE_SYM]
    out = []
    i = 1
    while True:
        a = base + i * row_size
        key = int.from_bytes(rom[a + row["ll_key"]:a + row["ll_key"] + 2], "big")
        if key == e["LL_KEY_AFTER"]:
            return out
        out.append((key, int.from_bytes(rom[a + row["ll_a"]:a + row["ll_a"] + 2], "big"),
                    int.from_bytes(rom[a + row["ll_b"]:a + row["ll_b"] + 2], "big"),
                    rom[a + row["ll_flags"]]))
        i += 1
        if i > 10000:
            raise CouldNotRun("%s has no trailing sentinel" % TABLE_SYM)


def pct(v):
    return "%.2f%%" % (100.0 * v / 127841)       # cycles in one NTSC frame (7.67 MHz / 60)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rom", required=True)
    ap.add_argument("--lst", required=True)
    ap.add_argument("--built-after", type=int, default=None)
    ap.add_argument("--cost", action="store_true", help="print the cycle note")
    ap.add_argument("--trajectory", default=None,
                    help="a loop_plane_probe/witness JSON with per-frame rows (x, y, state): "
                         "cost that real drive over this ROM's shipped table")
    ap.add_argument("--seeds", type=int, default=6)
    a = ap.parse_args(argv)
    if a.built_after is not None:
        rc = artifact_provenance.gate_check("layer_line_gate", a.rom, a.lst, a.built_after)
        if rc:
            return rc
    try:
        rom = pathlib.Path(a.rom).read_bytes()
        syms, e = parse_lst(a.lst)
        blk, row, row_size = layouts()
        span = extent(syms, SUBJECT)
        prog = decode(rom, span)
        runner = Runner(rom, prog, span, e, blk, row, row_size)
        null_cost, present_cost = caller_early_out(rom, syms, blk)
        kinds = {n: 0 for n in ("Vfwd", "Vback", "Hfwd", "Hback", "grounded_skip", "keep_path",
                                "prio_set", "prio_clear", "discontinuity")}
        fails, costs = [], []
        run_walks(runner, e, 1, a.seeds * 10, 400, fails, kinds, costs)
        shipped = shipped_rows(rom, syms, e, row, row_size)
        ship_note = "no shipped table (a canonical ROM: OJZ binds none)"
        if shipped is not None:
            skinds = {n: 0 for n in kinds}
            # walks around every shipped row, over the ROM's own table (the cursor points into ROM)
            for i, r in enumerate(shipped):
                cx = r[0] if not r[3] & (1 << e["LL_HORIZONTAL"]) else r[0] + 8
                cy = (r[1] + r[2]) // 2 if not r[3] & (1 << e["LL_HORIZONTAL"]) else r[1]
                run_walks(runner, e, 100 + i, 1, 120, fails, skinds, [], rows_override=shipped,
                          table_addr=syms[TABLE_SYM], box=(cx - 40, cx + 40, cy - 40, cy + 40))
            ship_note = ("shipped %s: %d rows, walked around every one (%d fires)"
                         % (TABLE_SYM, len(shipped),
                            sum(v for n, v in skinds.items() if n[0] in "VH")))
    except (CouldNotRun, UnsupportedInstruction, region_table.LayoutError) as exc:
        print("layer_line_gate: COULD NOT RUN — %s" % exc)
        return 2

    print("layer_line_gate [%s]: %s $%06X-$%06X (%d B) EXECUTED against Obj03's rule"
          % (a.lst, SUBJECT, span[0], span[1] - 1, span[1] - span[0]))
    print("  %d frames over %d synthetic tables; fires: %s" % (
        len(costs), a.seeds * 10, ", ".join("%s %d" % kv for kv in kinds.items())))
    print("  " + ship_note)
    vacuous = [n for n, v in kinds.items() if v == 0]
    if a.cost:
        by = {}
        for c, klass, _ in costs:
            by.setdefault(klass, []).append(c)
        print("  COST, per player per frame, MC68000UM cycles (a floor: no bus contention), "
              "Player_Main's share included (%d with no table; %d + the routine with one):"
              % (null_cost, present_cost))
        print("    act with NO table (the null test only)          %5d  (%s of a frame)"
              % (null_cost, pct(null_cost)))
        for klass, what in (("idle", "table, the player did not move"),
                            ("quiet", "table, moved, no line crossed"),
                            ("crossed", "table, a line crossed (fired or not)"),
                            ("discontinuity", "table, a teleport (> the step cap)")):
            v = sorted(by.get(klass, []))
            if v:
                print("    %-47s min %4d  median %4d  max %4d   (%d frames, synthetic "
                      "tables: denser than any shipped one)"
                      % (what, present_cost + v[0], present_cost + v[len(v) // 2],
                         present_cost + v[-1], len(v)))
        if a.trajectory:
            doc = json.loads(pathlib.Path(a.trajectory).read_text())
            pts = [(r["x"], r["y"], r.get("state") not in doc.get("grounded_states", []))
                   for r in doc["rows"] if "x" in r]
            if shipped is None:
                print("    --trajectory needs a ROM with a shipped table")
            else:
                cpu = runner.fresh(syms[TABLE_SYM], None, pts[0][0], pts[0][1], 0, 0, 0)
                per = []
                for x, y, air in pts[1:]:
                    runner.place(cpu, x, y, cpu.read(SST + e["SST_layer"], "b"),
                                 cpu.read(SST + e["SST_art_tile"], "w"),
                                 (1 << e["ST_IN_AIR"]) if air else 0)
                    tr, _ = runner.frame(cpu)
                    per.append(present_cost + tr["cycles"])
                per.sort()
                print("    REAL DRIVE %s (%d frames, this ROM's table): min %d, median %d, "
                      "max %d, mean %.0f (%s of a frame at the mean)"
                      % (pathlib.Path(a.trajectory).name, len(per), per[0], per[len(per) // 2],
                         per[-1], sum(per) / len(per), pct(sum(per) / len(per))))
    if fails:
        print("  FAIL — %d disagreement(s) with Obj03's rule:" % len(fails))
        for f in fails[:20]:
            print("    " + f)
        return 1
    if vacuous:
        print("  FAIL — VACUOUS: no frame exercised %s; an all-agree run that never fired "
              "those proves nothing about them" % ", ".join(vacuous))
        return 1
    print("  OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
