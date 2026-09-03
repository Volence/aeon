#!/usr/bin/env python3
"""The five VDP base registers stay DERIVED from the VRAM map, and every shipped
base survives the residue its register drops.

Run by `python3 -m pytest tools -q`, which build.sh runs BUILD-FATALLY (the pytest
lane around build.sh:589). That is this file's named runner.

WHY THIS EXISTS — the booked class, `docs/DEFERRED_WORK.md` "BASE-RESIDUE
ASSUMPTIONS WITHOUT AN `ensure` ARE INVISIBLE TO THE ALIGNMENT DECLARATION".
Registers $02/$03/$04/$05/$0D each carry a VRAM base encoded as the address bits
ABOVE a granule. The bits below are not rejected — they are DROPPED. So a base
that is misaligned, or a register byte that was transcribed from a base and then
left behind when the base moved, points the VDP at one address while every
`VRAM_*` consumer reads and writes another. Nothing downstream can see it: the
plane still renders, the sprites still draw, from the wrong VRAM.

TWO ASSERTIONS, AND THEY FAIL FOR DIFFERENT REASONS — both were live before this
parcel, because `BootData_VDPRegs` held five literals with the address they meant
recorded only in a trailing comment:

  1. DERIVATION — each of the five rows in the emitted table is the
     `vdp_base_reg`-folded const, not a literal. This is the half the .emp
     `ensure` cannot state: the guard lives INSIDE `vdp_base_reg`, so a row that
     goes back to `dc.b $5C` stops consulting it and the poison fixture
     (`poison_vdp_base_residue.emp`, the emp_expect_fail lane) keeps passing
     while the register has drifted. A guard nothing calls reports green.

  2. RESIDUE — every shipped base is a multiple of its register's granule. This
     restates in a second language what `vdp_base_reg`'s `ensure` says in `.emp`,
     deliberately: delete that `ensure` and the poison row goes red for the wall
     while this one goes red for the fact.

Every number is read out of the sources. Nothing here is typed: the bases come
from engine/system/constants.emp, the shifts and granules from the two exhaustive
`match`es in engine/vdp.emp. A value typed here would still agree after the thing
it mirrors moved, which is the whole failure mode being closed.

READ-ONLY: this file never writes into the repo.
"""

import pathlib
import re

import pytest

AEON = pathlib.Path(__file__).resolve().parent.parent
CONSTANTS = AEON / "engine" / "system" / "constants.emp"
VDP = AEON / "engine" / "vdp.emp"
BOOT_DATA = AEON / "engine" / "system" / "boot_data.emp"

# (VdpBase variant, engine.constants base name, VDP register number, the const
# boot_data.emp binds the fold to). The register numbers are the table's own row
# offsets, checked below against where each const actually appears.
REGISTERS = [
    ("PlaneA", "VRAM_PLANE_A", 0x02, "VDP_REG_PLANE_A"),
    ("Window", "VRAM_WINDOW", 0x03, "VDP_REG_WINDOW"),
    ("PlaneB", "VRAM_PLANE_B", 0x04, "VDP_REG_PLANE_B"),
    ("SpriteTable", "VRAM_SPRITE_TABLE", 0x05, "VDP_REG_SPRITES"),
    ("HScroll", "VRAM_HSCROLL_TABLE", 0x0D, "VDP_REG_HSCROLL"),
]


def _int(tok: str) -> int:
    return int(tok[1:], 16) if tok.startswith("$") else int(tok)


def emp_const(path: pathlib.Path, name: str) -> int:
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\$[0-9A-Fa-f]+|\d+)",
                  path.read_text(), re.M)
    assert m, f"{path.name}: no `const {name} = <int>` — this test reads it rather than typing it"
    return _int(m.group(1))


def match_arms(path: pathlib.Path, fn: str) -> dict[str, int]:
    """The variant -> int map of a `comptime fn`'s exhaustive `match`."""
    body = re.search(rf"comptime\s+fn\s+{re.escape(fn)}\s*\([^)]*\)[^{{]*\{{(.*?)\n\}}",
                     path.read_text(), re.S)
    assert body, f"{path.name}: no `comptime fn {fn}` — the arms are this test's authority"
    return {k: _int(v) for k, v in re.findall(r"^\s*(\w+)\s*=>\s*(\$[0-9A-Fa-f]+|\d+)\s*,",
                                              body.group(1), re.M)}


def vdp_regs_table() -> list[str]:
    """The `dc.b` operands of BootData_VDPRegs, in table order (register number = index)."""
    body = re.search(r"proc\s+BootData_VDPRegs\s*\([^)]*\)[^{]*\{(.*?)\n    \}",
                     BOOT_DATA.read_text(), re.S)
    assert body, "boot_data.emp: BootData_VDPRegs not found"
    return re.findall(r"^\s*dc\.b\s+(\S+)", body.group(1), re.M)


SHIFTS = match_arms(VDP, "vdp_base_shift")
GRANULES = match_arms(VDP, "vdp_base_granule")


@pytest.mark.parametrize("variant,base_name,regno,const_name", REGISTERS)
def test_register_row_is_derived_not_transcribed(variant, base_name, regno, const_name):
    """ASSERTION 1. The emitted row folds `vdp_base_reg`; it is not a literal byte.

    Red if anyone puts the literal back: that is the transcription defect this
    parcel closed, and it is invisible to the .emp guard, which only runs when
    something calls it.
    """
    rows = vdp_regs_table()
    assert regno < len(rows), (
        f"BootData_VDPRegs has {len(rows)} dc.b rows — no row for register ${regno:02X}")
    assert rows[regno] == const_name, (
        f"VDP register ${regno:02X} emits `{rows[regno]}`, not `{const_name}`. If that is a "
        f"literal, the byte no longer follows {base_name}: move the base and the VDP fetches "
        f"from the old address while every VRAM_* consumer uses the new one, with no "
        f"diagnostic anywhere.")

    src = BOOT_DATA.read_text()
    fold = re.search(rf"^\s*const\s+{re.escape(const_name)}\s*=\s*vdp_base_reg\(\s*"
                     rf"VdpBase\.{variant}\s*,\s*{re.escape(base_name)}\s*\)", src, re.M)
    assert fold, (
        f"boot_data.emp: `{const_name}` is not `vdp_base_reg(VdpBase.{variant}, {base_name})`. "
        f"The variant selects the shift AND the granule, so pairing it with the wrong base "
        f"encodes a correct-looking byte for the wrong region.")


@pytest.mark.parametrize("variant,base_name,regno,const_name", REGISTERS)
def test_shipped_base_survives_its_registers_granule(variant, base_name, regno, const_name):
    """ASSERTION 2. The shipped base is a multiple of the granule its register drops.

    The same fact `vdp_base_reg`'s `ensure` states in .emp, restated here so that
    deleting the guard leaves the fact still asserted by something.
    """
    base = emp_const(CONSTANTS, base_name)
    granule = GRANULES[variant]
    dropped = base & (granule - 1)
    assert dropped == 0, (
        f"{base_name} = {base:#06x} is not a multiple of register ${regno:02X}'s granule "
        f"{granule:#x}: the low {dropped:#x} is dropped by the encoding, so the VDP would "
        f"fetch from {base - dropped:#06x}.")

    value = base >> SHIFTS[variant]
    assert 0 <= value <= 0xFF, (
        f"{base_name} = {base:#06x} folds to {value:#x}, which does not fit the byte "
        f"register ${regno:02X} carries.")


def test_every_variant_has_both_arms():
    """The two exhaustive matches cover the same variant set this test drives.

    Without this, adding a sixth base register to one match and not the other, or
    to neither, would silently shrink what the two assertions above cover.
    """
    variants = {v for v, _, _, _ in REGISTERS}
    assert set(SHIFTS) == variants, (
        f"vdp_base_shift's arms {sorted(SHIFTS)} differ from the registers this test "
        f"knows about {sorted(variants)} — add the new one here too.")
    assert set(GRANULES) == variants, (
        f"vdp_base_granule's arms {sorted(GRANULES)} differ from the registers this test "
        f"knows about {sorted(variants)} — add the new one here too.")


def test_plane_b_has_one_address():
    """engine.constants spells the Plane B base twice; nothing used to pin them together.

    Reg $04 is derived from VRAM_PLANE_B while bg/plane_buffer/section address the
    plane through VRAM_PLANE_B_BYTES, so a split points the VDP at one nametable
    and the engine's writes at another. boot_data.emp carries the .emp `ensure`;
    this is the second-language twin, red even if that guard is deleted.
    """
    a = emp_const(CONSTANTS, "VRAM_PLANE_B")
    b = emp_const(CONSTANTS, "VRAM_PLANE_B_BYTES")
    assert a == b, (
        f"engine.constants disagrees with itself about Plane B: VRAM_PLANE_B = {a:#06x}, "
        f"VRAM_PLANE_B_BYTES = {b:#06x}.")
