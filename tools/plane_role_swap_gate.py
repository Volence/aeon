#!/usr/bin/env python3
"""EFFECTS-W1 DoD item 10b's BYTE GOLDEN — is the plane-role swap actually in the ROM,
and does it write the RIGHT byte to the RIGHT register on BOTH arms?

Design: docs/superpowers/designs/2026-09-03-vram-replan-item0-design.md §2 row 10b,
§2.0 and §8 Q4. Branch `parcel/item10b-plane-role-swap`.

WHY THIS GATE LOOKS DIFFERENT FROM item 11a's `plane_base_swap_gate.py`, stated up
front because a reader who knows that one will expect the mirror image of it: 11a's
mechanism (a mid-frame raster program) is a DEBUG-only effects-lab demonstration, so
its gate asserts OPPOSITE things in the two shapes — words present in DEBUG, the
symbol emitting zero bytes in release. Item 10b's mechanism is NOT a demo: it is real
engine capability (`engine.parallax.Parallax_Set_Roles_Swapped`, called every frame
from `Parallax_Update`'s register reassert) that a shipped game can use for a real
set-piece, so it is UNCONDITIONAL — the same bytes in both shapes. This gate therefore
asserts the SAME thing in both shapes: present and correct. That is still a real,
falsifiable claim (a future DEBUG-gating of the mechanism, or a fold regression that
only one shape's layout exposes, would turn it red), just not an opposite one.

THE CLAIM, PRECISELY. `Parallax_Set_Roles_Swapped` compiles to two arms:

    swapped (d0 != 0):  Set_VDP_Reg(2, vdp_base_reg(PlaneA, VRAM_PLANE_B))
                         Set_VDP_Reg(4, vdp_base_reg(PlaneB, VRAM_PLANE_A))
    normal  (d0 == 0):  Set_VDP_Reg(2, vdp_base_reg(PlaneA, VRAM_PLANE_A))
                         Set_VDP_Reg(4, vdp_base_reg(PlaneB, VRAM_PLANE_B))

Each `Set_VDP_Reg` call is a `move.w #<reg>, d0` immediately followed (a `bsr`/`bra` to
the shared helper sits between, which this gate skips over) by `move.b #<value>, d1`.
This gate DISASSEMBLES the routine (capstone, the same library `sprite_tilt_gate.decode`
already uses elsewhere in this tree — reused, not re-implemented) and asserts the four
(register, value) pairs appear in this exact order. That catches BOTH classes of bug a
pure comptime `ensure` cannot see: the fold producing the wrong byte (11a's own
argument — a comptime `ensure` proves two constants differ, never that the compiled
instruction stream actually carries them), AND a hand-written mixup this parcel's `.emp`
has no `ensure` over at all — e.g. the swapped arm writing register 2 the NORMAL value,
or the two `Set_VDP_Reg` calls landing in the wrong order.

THE EXPECTATION IS DERIVED FROM FILES THE FIXTURE DOES NOT AUTHOR:
  * `VRAM_PLANE_A` / `VRAM_PLANE_B`        engine/system/constants.emp
  * `vdp_base_shift`'s PlaneA/PlaneB arms  engine/vdp.emp (the same fold
                                           engine/system/boot_data.emp and item 11a's
                                           OJZ_BaseSwap both derive their own words from)

WHAT IT CANNOT SAY. This is a ROM-image check. It proves the mechanism's four register
writes reach the ROM correctly; it does NOT prove the VDP actually draws the swapped
picture, nor that the HScroll/VSRAM feed-packer sites (Parallax_Fill_PerLine,
Parallax_Step5_Vscroll) swap their pack order correctly — those are per-line/per-column
runtime behaviour a static ROM-image gate cannot observe. That needs an emulator, which
this lane does not have, and it is TAGGED in the parcel's DEFERRED_WORK entry. Do not
read a green here as the picture having been looked at.

REFUSES TO BE VACUOUS. A missing symbol, an extent capstone cannot decode cleanly, fewer
than four (register, value) pairs found, or a constant this file cannot parse out of its
source is reported as UNMEASURABLE (exit 2), never as a pass.

Usage:
    tools/plane_role_swap_gate.py --shape debug|release [--lst s4.lst] [--rom s4.bin]
                                  [--built-after <epoch s>]

Exit 0 = the mechanism is in the ROM and correct. 1 = a real failure. 2 = UNMEASURABLE.
"""

import os
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
REPO = os.path.dirname(REPO)

CONSTANTS = os.path.join(REPO, "engine", "system", "constants.emp")
VDP = os.path.join(REPO, "engine", "vdp.emp")

SYM = "Parallax_Set_Roles_Swapped"
NEXT_SYM = "Parallax_Update"
# The local `.normal:` label, mangled exactly as sigil's listing spells every other
# local label in this file (measured against s4.debug.lst rather than assumed):
# `$<module>$<proc>$<label>`.
NORMAL_LABEL = "$engine.parallax$Parallax_Set_Roles_Swapped$normal"

from plane_base_swap_gate import (  # noqa: E402
    Unmeasurable, emp_const, vdp_base_shift, lst_labels, at,
)
from sprite_tilt_gate import decode  # noqa: E402


def expected_pairs(plane_a, plane_b, shift_a, shift_b):
    """The four (register, value) pairs, in the order the compiled routine must carry
    them. A PURE function over the four derived facts — exercised without a ROM at all
    by tools/test_plane_role_swap_gate.py.
    """
    a_normal = plane_a >> shift_a
    a_swapped = plane_b >> shift_a
    b_normal = plane_b >> shift_b
    b_swapped = plane_a >> shift_b
    if a_normal == a_swapped:
        raise Unmeasurable(
            f"Plane A (${plane_a:04X}) and Plane B (${plane_b:04X}) fold to the SAME "
            f"reg $02 byte at shift {shift_a}, so there is no role swap to look for. "
            f"The `.emp` fixture refuses this by name too; seeing it here means that "
            f"ensure is no longer running")
    if b_normal == b_swapped:
        raise Unmeasurable(
            f"Plane A (${plane_a:04X}) and Plane B (${plane_b:04X}) fold to the SAME "
            f"reg $04 byte at shift {shift_b}, so there is no role swap to look for. "
            f"The `.emp` fixture refuses this by name too; seeing it here means that "
            f"ensure is no longer running")
    return [(2, a_swapped), (4, b_swapped), (2, a_normal), (4, b_normal)]


def _imm(op):
    """`#$38` -> 0x38, or None if `op` is not an immediate."""
    op = op.strip()
    if not op.startswith("#$"):
        return None
    try:
        return int(op[2:], 16)
    except ValueError:
        return None


def _reg_num(op):
    """`d1` -> 1, or None."""
    op = op.strip()
    if len(op) == 2 and op[0] == "d" and op[1] in "01234567":
        return int(op[1])
    return None


def found_pairs(rom, start, end):
    """Walk the disassembly for `move.w #<n>, d0` / `move.b #<n>, d1` instructions, in
    address order, and return the (n, m) pairs a `move.w #n,d0` followed (anywhere
    later in the extent — a `bsr`/`bra` sits between the two in this routine) by the
    NEXT `move.b #m,d1` forms. Anything else in the extent (the flag store, `tst.b`,
    `beq`, the `bsr`/`bra` to the shared helper) is ignored — this function looks for
    exactly the shape `Set_VDP_Reg`'s two argument loads make, nothing more.
    """
    _, listing = decode(rom, start, end)
    pairs = []
    pending_reg = None
    for _addr, _hexb, mnemonic, op_str in listing:
        ops = [o.strip() for o in op_str.split(",")] if op_str else []
        if mnemonic == "move.w" and len(ops) == 2 and _reg_num(ops[1]) == 0:
            imm = _imm(ops[0])
            if imm is not None:
                pending_reg = imm
                continue
        if mnemonic == "move.b" and len(ops) == 2 and _reg_num(ops[1]) == 1:
            imm = _imm(ops[0])
            if imm is not None and pending_reg is not None:
                pairs.append((pending_reg, imm))
                pending_reg = None
    return pairs


def main():
    args = sys.argv[1:]

    def opt(flag, default=None):
        return args[args.index(flag) + 1] if flag in args else default

    lst = opt("--lst", "s4.lst")
    rom_name = opt("--rom", "s4.bin")
    shape = opt("--shape")
    built_after = opt("--built-after")
    lst_path = lst if os.path.isabs(lst) else os.path.join(REPO, lst)
    rom_path = rom_name if os.path.isabs(rom_name) else os.path.join(REPO, rom_name)

    try:
        if shape not in ("debug", "release"):
            raise Unmeasurable(
                f"--shape must be `debug` or `release` (got {shape!r}). Unlike item "
                f"11a's gate this one asserts the SAME thing in both shapes — but it "
                f"still refuses to guess which shape it is reading from an artifact's "
                f"NAME, for the same reason 11a's does")
        for p in (lst_path, rom_path):
            if not os.path.isfile(p):
                raise Unmeasurable(f"{p} does not exist")
        if built_after is not None:
            try:
                t0 = float(built_after)
            except ValueError:
                raise Unmeasurable(f"--built-after {built_after!r} is not a number of seconds")
            for p in (lst_path, rom_path):
                if os.path.getmtime(p) < t0:
                    raise Unmeasurable(
                        f"{os.path.basename(p)} predates this invocation's sigil run; "
                        f"it is a PREVIOUS build's artifact and reading it would "
                        f"measure the past")

        plane_a = emp_const(CONSTANTS, "VRAM_PLANE_A")
        plane_b = emp_const(CONSTANTS, "VRAM_PLANE_B")
        shift_a = vdp_base_shift("PlaneA")
        shift_b = vdp_base_shift("PlaneB")
        want = expected_pairs(plane_a, plane_b, shift_a, shift_b)

        labels = lst_labels(lst_path)
        start = at(labels, SYM, lst_path)
        end = at(labels, NEXT_SYM, lst_path)
        if NORMAL_LABEL not in labels:
            raise Unmeasurable(
                f"`{NORMAL_LABEL}` is not in {os.path.relpath(lst_path, REPO)}. This "
                f"gate splits the routine's two arms at that local label; a missing "
                f"label means the source no longer names its `.normal:` arm this way, "
                f"or sigil's local-label mangling changed")
        normal_addr = labels[NORMAL_LABEL]

        with open(rom_path, "rb") as f:
            rom = f.read()
        if end > len(rom):
            raise Unmeasurable(
                f"`{SYM}` at ${start:06X} .. `{NEXT_SYM}` at ${end:06X} runs past the "
                f"end of the {len(rom)}-byte ROM")

        got = found_pairs(rom, start, end)

        print(f"plane_role_swap_gate [{os.path.basename(lst_path)}, shape={shape}]")
        print(f"  derived: Plane A ${plane_a:04X}, Plane B ${plane_b:04X}, "
              f"vdp_base_shift(PlaneA)={shift_a} vdp_base_shift(PlaneB)={shift_b}")
        print(f"  want (reg, value): {[(r, f'${v:02X}') for r, v in want]}")
        print(f"  {SYM} at ${start:06X}, {NORMAL_LABEL} at ${normal_addr:06X}, "
              f"{NEXT_SYM} at ${end:06X}")
        print(f"  got  (reg, value): {[(r, f'${v:02X}') for r, v in got]}")

        if len(got) != 4:
            print(f"plane_role_swap_gate: FAIL — found {len(got)} (register, value) "
                  f"pair(s) in `{SYM}`'s [${start:06X},${end:06X}) extent, want "
                  f"exactly 4 (two Set_VDP_Reg calls per arm, two arms). Either the "
                  f"routine no longer calls Set_VDP_Reg this way, or capstone decoded "
                  f"something this gate's pattern does not recognise — rerun with the "
                  f"`decode` listing printed to see why.")
            return 1

        if got != want:
            bad = [i for i, (g, w) in enumerate(zip(got, want)) if g != w]
            print(f"plane_role_swap_gate: FAIL — pair(s) {bad} differ from the derived "
                  f"expectation.")
            for i, (g, w) in enumerate(zip(got, want)):
                if g != w:
                    print(f"    index {i}: got (d0=${g[0]:X}, d1=${g[1]:02X}) want "
                          f"(d0=${w[0]:X}, d1=${w[1]:02X})")
            print(f"    Reminder: index 0-1 are the SWAPPED arm (before "
                  f"{NORMAL_LABEL}, ${normal_addr:06X}), index 2-3 are the NORMAL arm.")
            return 1

        print(f"plane_role_swap_gate: OK — Parallax_Set_Roles_Swapped writes reg $02/"
              f"$04 correctly on both arms: swapped ${want[0][1]:02X}/${want[1][1]:02X}, "
              f"normal ${want[2][1]:02X}/${want[3][1]:02X}")
        return 0

    except Unmeasurable as e:
        print(f"plane_role_swap_gate: UNMEASURABLE — {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
