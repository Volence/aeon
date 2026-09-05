#!/usr/bin/env python3
"""loop_crossover_cost.py — re-sum Player_LoopCrossover's cost note from the bytes the
build actually emitted.

WHY THIS EXISTS. The cost block in `Player_LoopCrossover`'s comment
(games/sonic4/player/player_common.emp) is the kind of number that goes stale in silence:
an earlier draft of it put Collision_GetType at ~150 cycles and was wrong by a factor of
two, and nothing noticed until someone summed the real encodings. So the figures are not
written beside the source and trusted — they are PRODUCED here, from

  * the instruction stream `tools/loop_crossover_gate.py` executes, which is decoded by
    capstone out of the built ROM and is therefore the encodings the build emitted, not
    the assembler's opinion or the author's memory; and
  * one cycle table, below, transcribed from the MC68000UM instruction-timing tables.

Every form the two routines contain has an entry; anything else RAISES. A form that
appears after an edit stops this tool rather than being summed as zero — the same
contract the gate's executor keeps, and for the same reason.

WHAT IT CANNOT SEE, said plainly so a green here is not over-read: this is the 68000's
own instruction timing. It does not model the bus contention a real Mega Drive imposes
(VDP/DMA/Z80 stealing cycles from the 68000), so every figure is a floor for the CPU's
own work and the frame-share percentages derived from it are floors too. That is the
same basis every other cycle figure in this engine's comments is quoted on, so they
remain comparable with each other.

Usage:

    tools/loop_crossover_cost.py --lst s4.debug.lst --rom s4.debug.bin
"""

import argparse
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import loop_crossover_gate as lxg                      # noqa: E402
from sprite_tilt_gate import UnsupportedInstruction     # noqa: E402


# --------------------------------------------------------------------------
# The cycle table — MC68000UM section 8, 16-bit bus, no wait states
# --------------------------------------------------------------------------

# Table 8-1/8-2, effective-address calculation. Keyed by the gate's operand grammar.
_EA = {
    "d":    (0, 0),          # Dn
    "a":    (0, 0),          # An
    "imm":  (4, 8),          # #<data>
    "disp": (8, 12),         # (d16,An)
    "idx":  (10, 14),        # (d8,An,Xn)
    "absw": (8, 12),         # (xxx).W
    "absl": (12, 16),        # (xxx).L
    "predec": (6, 10),       # -(An)   — the ALU form; MOVE's destination differs
    "postinc": (4, 8),       # (An)+
}

# MOVE's DESTINATION cost (Tables 8-5/8-6). It is not the ALU ea cost: a MOVE into
# -(An) costs 4/8, where an ALU operand at -(An) costs 6/10.
_EA_MOVE_DST = dict(_EA, predec=(4, 8))


def _ea(form, size, table=_EA):
    if form[0] not in table:
        raise UnsupportedInstruction("no ea timing for operand form %r" % (form,))
    b_w, lng = table[form[0]]
    return lng if size == "l" else b_w


def _cycles(mnem_full, ops, taken):
    """Cycles for ONE executed instruction. `taken` is meaningful only for Bcc."""
    parts = mnem_full.split(".")
    base = parts[0]
    size = parts[1] if len(parts) > 1 else "w"

    if base == "rts":
        return 16
    if base == "swap":
        return 4
    if base == "moveq":
        return 4
    if base == "nop":
        return 4
    if base == "bra":
        return 10
    if base in lxg.BRANCHES:
        # Bcc: byte displacement 10 taken / 8 not taken; word 10 taken / 12 not taken.
        # The displacement width is not in capstone's mnemonic, so it is taken from the
        # encoded instruction length by the caller (see `sum_path`), which passes it in
        # `taken` as a (taken, is_word) pair.
        hit, is_word = taken
        if is_word:
            return 10 if hit else 12
        return 10 if hit else 8
    if base in ("jsr", "bsr"):
        if base == "bsr":
            return 18
        form = ops[0][0]
        return {"absw": 18, "absl": 20, "a": 16, "disp": 18, "tgt": 18}[form]
    if base == "lea":
        return {"absw": 8, "absl": 12, "disp": 8, "a": 4, "idx": 12}[ops[0][0]]
    if base in ("move", "movea"):
        return 4 + _ea(ops[0], size) + _ea(ops[1], size, _EA_MOVE_DST)
    if base == "tst":
        return 4 + _ea(ops[0], size)
    if base in ("andi", "ori", "eori", "addi", "subi"):
        if ops[1][0] != "d":
            raise UnsupportedInstruction("%s to a non-Dn destination not timed" % base)
        return 16 if size == "l" else 8
    if base == "cmpi":
        if ops[1][0] != "d":
            raise UnsupportedInstruction("cmpi to a non-Dn destination not timed")
        return 14 if size == "l" else 8
    if base in ("addq", "subq"):
        if ops[1][0] not in ("d", "a"):
            raise UnsupportedInstruction("%s to memory not timed" % base)
        return 8 if size == "l" else 4
    if base in ("add", "sub", "and", "or", "cmp", "eor"):
        if ops[1][0] != "d":
            raise UnsupportedInstruction("%s <ea>,<mem> not timed" % base)
        if size == "l":
            # long: 6 + ea, but a register or immediate source costs 8 flat
            return 8 if ops[0][0] in ("d", "a", "imm") else 6 + _ea(ops[0], size)
        return 4 + _ea(ops[0], size)
    if base in ("lsr", "lsl", "asr", "asl"):
        if ops[0][0] != "imm":
            raise UnsupportedInstruction("register-count shift not timed")
        n = ops[0][1] or 8
        return (8 if size == "l" else 6) + 2 * n
    raise UnsupportedInstruction("instruction not timed: %s" % mnem_full)


def sum_path(trace, prog):
    """Sum one recorded execution. Branch taken/not-taken is READ OFF the trace: the
    instruction after a branch is either its fall-through or its target, so nothing here
    has to predict what the routine did."""
    total = 0
    insns = trace.insns
    for i, (pc, mnem, ops) in enumerate(insns):
        base = mnem.split(".")[0]
        arg = None
        if base in lxg.BRANCHES and base != "bra":
            nxt = prog[pc][2]
            is_word = (nxt - pc) == 4          # 2 bytes opcode + 2 displacement
            hit = (i + 1 < len(insns)) and insns[i + 1][0] != nxt
            arg = (hit, is_word)
        total += _cycles(mnem, ops, arg)
    return total


# --------------------------------------------------------------------------
# The scenarios — one per row of the cost note
# --------------------------------------------------------------------------

def scenarios(rom, prog, extents, syms, equs):
    K = equs
    cw, ch = K["COLL_CELL_W"], K["COLL_CELL_H"]
    base = (lxg.IN_CELL[0] & ~(cw - 1), lxg.IN_CELL[1] & ~(ch - 1))

    def world(plane_a_attr=lxg.ATTR_A, plane_b_attr=lxg.ATTR_A, mark=None,
              mark_attr=lxg.ATTR_A):
        w = lxg.World(rom, prog, extents, syms, K)
        w.fill_plane(0, plane_a_attr)
        w.fill_plane(1, plane_b_attr)
        if mark is not None:
            w.set_crossover(mark_attr, mark)
        return w

    def run(w, first, second, layer, vel):
        """Settle on `first`, then take the step to `second`, and return the SECOND
        frame's cycle count — the one the cost row describes."""
        w.set_x_vel(vel)
        w.place(first[0], first[1], layer)
        w.frame()
        w.cpu.wb(lxg.SST + K["SST_layer"], layer)
        w.place(second[0], second[1], layer)
        return sum_path(w.frame(), prog)

    rows = []

    # the steady state: the position did not leave its cell
    w = world()
    rows.append(("same cell (the whole steady state)",
                 run(w, base, (base[0] + 1, base[1]), K["LAYER_PATH_A"], lxg.RIGHT)))

    # off the tile cache — GetType's early air exit
    w = world()
    rows.append(("cell changed, position off the tile cache",
                 run(w, (0xF000, 0xF000), (0xF000 + cw, 0xF000),
                     K["LAYER_PATH_A"], lxg.RIGHT)))

    # one cell of X, no mark, on each plane
    for plane, name in ((K["LAYER_PATH_A"], "plane A"), (K["LAYER_PATH_B"], "plane B")):
        w = world()
        rows.append(("cell changed, one cell of X, no mark (%s)" % name,
                     run(w, base, (base[0] + cw, base[1]), plane, lxg.RIGHT)))

    # one cell DIAGONALLY, no mark
    w = world()
    rows.append(("cell changed, one cell DIAGONALLY, no mark (plane A)",
                 run(w, base, (base[0] + cw, base[1] + ch),
                     K["LAYER_PATH_A"], lxg.RIGHT)))

    # a mark that FIRES, both directions
    w = world(mark=K["XOVER_TO_B"])
    rows.append(("cell changed, one cell, FIRES rightward (TO_B, plane A)",
                 run(w, base, (base[0] + cw, base[1]), K["LAYER_PATH_A"], lxg.RIGHT)))
    w = world(mark=K["XOVER_TO_A"])
    rows.append(("cell changed, one cell, FIRES leftward (TO_A, plane B)",
                 run(w, base, (base[0] - cw, base[1]), K["LAYER_PATH_B"], lxg.LEFT)))

    # a mark REFUSED by the direction gate — the new rows
    w = world(mark=K["XOVER_TO_A"])
    rows.append(("cell changed, one cell, mark REFUSED (TO_A, travelling right)",
                 run(w, base, (base[0] + cw, base[1]), K["LAYER_PATH_B"], lxg.RIGHT)))
    w = world(mark=K["XOVER_TO_B"])
    rows.append(("cell changed, one cell, mark REFUSED (TO_B, travelling left)",
                 run(w, base, (base[0] - cw, base[1]), K["LAYER_PATH_A"], lxg.LEFT)))
    w = world(mark=K["XOVER_TO_B"])
    rows.append(("cell changed, one cell, mark REFUSED (x_vel == 0)",
                 run(w, base, (base[0], base[1] + ch), K["LAYER_PATH_A"], lxg.STILL)))

    # a discontinuity — beyond the sweep's reach, so one probe at the endpoint. The
    # step is one cell PAST the reach and no further, so the destination is still inside
    # the tile cache: a distant teleport would leave the window and be graded as the
    # off-cache row instead, which is a different path and a different number.
    w = world()
    over = ((XOVER_SWEEP_REACH_X(K) // cw) + 1) * cw
    rows.append(("a discontinuity (teleport/respawn/act start), snapped to one probe",
                 run(w, base, (base[0] + over, base[1]), K["LAYER_PATH_A"], lxg.RIGHT)))

    # two cells of X in one frame — the step-over the sweep exists for
    w = world()
    rows.append(("TWO cells of X in one frame, no mark",
                 run(w, base, (base[0] + 2 * cw, base[1]),
                     K["LAYER_PATH_A"], lxg.RIGHT)))
    w = world(mark=K["XOVER_TO_B"])
    rows.append(("TWO cells of X in one frame, marked field, fires on both",
                 run(w, base, (base[0] + 2 * cw, base[1]),
                     K["LAYER_PATH_A"], lxg.RIGHT)))
    return rows


def XOVER_SWEEP_REACH_X(K):
    """The sweep's horizontal reach, re-derived here the way the .emp derives it:
    the ground-speed cap rounded UP to a whole number of collision cells."""
    cw = K["COLL_CELL_W"]
    px = K["PHYS_GSP_CAP"] >> 8
    return ((px + cw - 1) // cw) * cw


# The caller's own `jbsr Player_LoopCrossover` in Player_Main, which relaxes to a
# `bsr.w` (18 cycles). Every row below includes it, because the cost note it feeds has
# always been quoted on that basis — its steady-state list opens with "bsr.w 18" — and a
# table that silently changed basis would look like a free 18-cycle saving.
CALL_IN = 18

NTSC_FRAME = 127800     # 68000 cycles in one NTSC frame at 7.67 MHz / 59.92 Hz


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lst", required=True)
    ap.add_argument("--rom", required=True)
    ap.add_argument("--players", type=int, default=2)
    args = ap.parse_args()

    rom = pathlib.Path(args.rom).read_bytes()
    syms, equs = lxg.parse_lst(args.lst)
    spans = [lxg.routine_extent(syms, lxg.READ_SITE),
             lxg.routine_extent(syms, lxg.LOOKUP)]
    prog, _ = lxg.decode(rom, spans)
    extents = [tuple(s) for s in spans]

    print("loop_crossover_cost [%s]" % args.lst)
    print("  %s %d bytes, %s %d bytes — cycles summed from the EMITTED encodings"
          % (lxg.READ_SITE, spans[0][1] - spans[0][0],
             lxg.LOOKUP, spans[1][1] - spans[1][0]))
    print("  MC68000UM instruction timing only; no VDP/DMA/Z80 bus contention, so every")
    print("  figure is a floor for the 68000's own work. Each row includes the caller's")
    print("  bsr.w (%d), the basis the cost note has always been quoted on." % CALL_IN)
    print()
    rows = [(n, c + CALL_IN) for n, c in scenarios(rom, prog, extents, syms, equs)]
    width = max(len(n) for n, _ in rows)
    for name, cyc in rows:
        print("  %-*s  %5d" % (width, name, cyc))
    print()
    for name, cyc in rows:
        share = 100.0 * cyc * args.players / NTSC_FRAME
        print("  %-*s  %5.2f%% of an NTSC frame, %d player(s)"
              % (width, name, share, args.players))
    return 0


if __name__ == "__main__":
    sys.exit(main())
