#!/usr/bin/env python3
"""region_table — the act's Region table read out of a ROM image, and `Region_Resolve`
restated against it. ONE copy for every out-of-assembler reader.

WHY THIS EXISTS. Painted-regions v1 (docs/superpowers/designs/2026-09-09-regions-v1-design.md)
moved the act's identity scope from the section grid to a table of rectangles, and five
tools (the parallax crossing gate, the boot-override gate, the sec5 band witness, the row
remap witness, the blank-priority probe, and the preset lab witness) need to ask "which
region contains this camera centre" of a ROM they did not build. Five hand-copied answers
would drift five ways; this module is the one answer, and it is kept honest two ways:

  * The LAYOUT is parsed out of `engine/structs.emp`, never typed. Offsets are accumulated
    from the field TYPES and every trailing `// $HH` comment is cross-checked against the
    accumulation, and a declared `(size: N)` is cross-checked against the total. A field
    inserted without renumbering is a `LayoutError`, not a four-byte slide.
  * The RESOLVE restates `Region_Resolve` (engine/level/parallax.emp): the FIRST row, in
    table order, whose inclusive rectangle contains the point, compared UNSIGNED; None when
    no row does. The act constructor proves no two rows overlap and that the rows tile the
    act, so "first" and "only" are the same row on any tree that builds.

tools/test_region_table.py holds both properties, and poisons each on purpose.
"""
from __future__ import annotations

import re
from pathlib import Path

AEON = Path(__file__).resolve().parent.parent
STRUCTS = "engine/structs.emp"

_SCALAR = {"u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4}

# The fields every consumer of this module reads, by name. A rename in structs.emp makes
# `region_layout` refuse naming the missing field, rather than every consumer KeyError-ing.
#
# tools/test_region_table.py asserts this list EQUALS the declaration's field order, not that
# it is contained in it, which is why a field appended to `struct Region` lands here in the
# same change rather than being silently unread. Regions part 2 step 1 (2026-09-15) added the
# last two: nothing in the ENGINE reads them yet, but this module is the out-of-assembler
# reader and a row it hands back with the background half missing would be a half-read record.
REGION_FIELDS = ("rg_x0", "rg_x1", "rg_y0", "rg_y1", "rg_effects", "rg_parallax",
                 "rg_bg_layout", "rg_bg_span", "rg_bg_tiles")
ACT_REGION_FIELDS = ("act_regions", "act_region_count")


class LayoutError(Exception):
    """The source's own statements about a layout disagree, or a field this module reads is
    missing. Consumers treat it as a SETUP error (the measurement could not be made)."""


def _field_size(ty: str) -> int:
    ty = ty.strip()
    if ty.startswith("*"):
        return 4
    if ty in _SCALAR:
        return _SCALAR[ty]
    raise LayoutError(f"unknown field type `{ty}` — teach region_table._field_size about it "
                      "rather than guessing an offset")


def struct_layout(name: str, text: str | None = None, rel: str = STRUCTS,
                  aeon: Path = AEON) -> tuple[dict[str, int], int]:
    """Field name -> byte offset, and the total size, out of the `.emp` declaration.

    Every `// $HH` offset comment is compared with the offset accumulated from the types, and
    a declared `(size: N)` with the total: two independent statements checked against each
    other, so a stale comment stops the reader instead of misleading it.
    """
    if text is None:
        text = (aeon / rel).read_text()
    m = re.search(rf"^\s*(?:pub\s+)?struct\s+{re.escape(name)}\b([^{{]*)\{{(.*?)^\}}",
                  text, re.M | re.S)
    if not m:
        raise LayoutError(f"cannot find `struct {name}` in {rel}")
    head, body = m.group(1), m.group(2)
    off, out = 0, {}
    for raw in body.splitlines():
        line = raw.split("//")[0]
        fm = re.match(r"\s*(\w+)\s*:\s*([^=@,]+?)\s*(?:=\s*[^,]+)?,", line)
        if not fm:
            continue
        fname, ty = fm.group(1), fm.group(2)
        cm = re.search(r"//.*?\$([0-9A-Fa-f]+)", raw)
        if cm and int(cm.group(1), 16) != off:
            raise LayoutError(f"{rel} `struct {name}`: field `{fname}` is commented at "
                              f"${int(cm.group(1), 16):02X} but the fields before it total "
                              f"${off:02X} — the declaration and its offset comments disagree")
        out[fname] = off
        off += _field_size(ty)
    if not out:
        raise LayoutError(f"parsed no fields out of `struct {name}` in {rel}")
    sm = re.search(r"\(\s*size\s*:\s*(\$[0-9A-Fa-f]+|\d+)\s*\)", head)
    if sm:
        declared = int(sm.group(1)[1:], 16) if sm.group(1).startswith("$") else int(sm.group(1))
        if declared != off:
            raise LayoutError(f"{rel} `struct {name}` declares (size: {declared}) but its "
                              f"fields total {off}")
    return out, off


def region_layout(text: str | None = None, aeon: Path = AEON) -> tuple[dict[str, int], int]:
    off, size = struct_layout("Region", text, aeon=aeon)
    missing = [f for f in REGION_FIELDS if f not in off]
    if missing:
        raise LayoutError(f"`struct Region` no longer declares {missing} — every region reader "
                          "reads those by name")
    return off, size


def act_region_offsets(text: str | None = None, aeon: Path = AEON) -> dict[str, int]:
    off, _ = struct_layout("Act", text, aeon=aeon)
    missing = [f for f in ACT_REGION_FIELDS if f not in off]
    if missing:
        raise LayoutError(f"`struct Act` no longer declares {missing}")
    return {f: off[f] for f in ACT_REGION_FIELDS}


def _u(rom: bytes, at: int, n: int) -> int:
    if at < 0 or at + n > len(rom):
        raise LayoutError(f"ROM read of {n} bytes at {at:#x} is outside the {len(rom)}-byte image")
    return int.from_bytes(rom[at:at + n], "big")


def read_regions(rom: bytes, act_base: int, aeon: Path = AEON) -> list[dict]:
    """The act's region rows, in table order, read out of `rom` through the act descriptor at
    `act_base` (a ROM offset, e.g. the listing's OJZ_Act1_Descriptor)."""
    ro, rsize = region_layout(aeon=aeon)
    ao = act_region_offsets(aeon=aeon)
    base = _u(rom, act_base + ao["act_regions"], 4)
    count = _u(rom, act_base + ao["act_region_count"], 2)
    if count == 0:
        raise LayoutError("Act.act_region_count is 0 — the act constructor forbids that, so "
                          "this is not the ROM the source describes")
    rows = []
    for i in range(count):
        a = base + i * rsize
        rows.append({
            "index": i, "addr": a,
            "x0": _u(rom, a + ro["rg_x0"], 2), "x1": _u(rom, a + ro["rg_x1"], 2),
            "y0": _u(rom, a + ro["rg_y0"], 2), "y1": _u(rom, a + ro["rg_y1"], 2),
            "effects": _u(rom, a + ro["rg_effects"], 4),
            "parallax": _u(rom, a + ro["rg_parallax"], 4),
            # Regions part 2 step 1. 0 in either means "the act's own" — the layout defaults
            # to Act.act_bg_layout and the span to PLANE_B_SPAN — so a caller reads 0 as the
            # sentinel, never as an address or a height.
            "bg_layout": _u(rom, a + ro["rg_bg_layout"], 4),
            "bg_span": _u(rom, a + ro["rg_bg_span"], 2),
            # Region bg switch (2026-09-16). 0 = the act's own tiles (Act.act_bg_tiles).
            "bg_tiles": _u(rom, a + ro["rg_bg_tiles"], 4),
        })
    return rows


def region_at(rows: list[dict], x: int, y: int) -> dict | None:
    """`Region_Resolve` restated: the first row whose INCLUSIVE rectangle contains (x, y),
    both compared as unsigned words, or None (the proc's a0 = 0)."""
    x &= 0xFFFF
    y &= 0xFFFF
    for r in rows:
        if r["x0"] <= x <= r["x1"] and r["y0"] <= y <= r["y1"]:
            return r
    return None
