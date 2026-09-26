#!/usr/bin/env python3
"""s2_layer_lines.py — Sonic 2's plane-switcher lines, baked into a clip act's layer-line table.

WHAT THIS IS FOR (S2CLIP-PLANE-SWITCH, docs/research/2026-09-26-s2clip-loops-planes.md). Sonic 2
moves the player between its two collision paths with Obj03, the plane switcher
(s2.asm `Obj03:`): a LINE in the level, with a remembered side per player, that sets the path
and, independently, the player's draw priority when he crosses it. A clip act carries no Sonic 2
objects, so without this nothing ever moved the player off path A and none of Emerald Hill's
loops could be completed. This module reads every Obj03 of each clip's donor zone out of the
disassembly's own object layout, keeps the ones inside the clip's source rectangle, moves them
to act coordinates and turns them into rows of the engine's `LayerLine` table
(engine/structs.emp), which `Player_LayerLines` (games/sonic4/player/player_common.emp) runs
every frame with Obj03's rule.

ONE BAKE PATH (LINES-EVERYWHERE, 2026-09-26). This file is the DONOR SOURCE only: it reads Obj03
records into line records. Cutting them into rows, sorting, the L4 refusal and spelling the rows
as `.emp` are tools/layer_lines.py's, shared with the other source (an act's authored
layer_lines.json). `rows`, `rows_text`, `engine_constants` and `LayerLineError` are re-exported
from there under their old names.

THE ROW FORMAT. One 8-byte `LayerLine` per row, sorted by `ll_key`, between two sentinel rows
(LL_KEY_BEFORE first, LL_KEY_AFTER last):

    vertical line    ll_key = the line's X           ll_a/ll_b = its Y extent [y - half, y + half)
    horizontal line  ll_key = a segment's left X     ll_a = the line's Y
                     ll_b = the segment's right X (exclusive)

A horizontal line is cut into segments no wider than LL_SEG_W, so every row's X interest starts
within LL_SEG_W of where it can matter. That is what lets the runtime window over the sorted
table stay LL_SEG_W plus one frame's step wide instead of 2 x $100 (Obj03's longest line). The
segments partition the line's extent, so a crossing fires exactly one of them: the crossing
Obj03 would make, once.

`ll_flags` is Obj03's subtype re-packed. The bit numbers are the engine's LL_* constants, read
out of engine/system/constants.emp, so this file cannot disagree with the consumer:

    LL_KEEP_PATH   the layout word's x-flip (bit 13): leave the path, change priority only
    LL_GROUNDED    subtype bit 7: only while the player is on the ground
    LL_HORIZONTAL  subtype bit 2
    LL_FWD_B       subtype bit 3: crossing right (or down) puts him on path B, else path A
    LL_BACK_B      subtype bit 4: crossing left (or up), the same
    LL_FWD_HI      subtype bit 5: crossing right (or down) draws him at high priority
    LL_BACK_HI     subtype bit 6: crossing left (or up), the same

Subtype bits 1:0 (the length) become the extent and are not carried. On an LL_KEEP_PATH line
the two path bits mean nothing (Obj03 skips the path write), so they are cleared: the ROM
carries no bit its reader ignores.

THE ORDER. Rows are sorted by `ll_key` and, on equal keys, by the donor's own object-layout
order. That second key is Sonic 2's execution order: its objects manager loads a layout's
records in file order into ascending object slots and runs them in slot order, so where two
lines overlap (CPZ (1048, 580) and (1048, 704) share y 640..643) the one Sonic 2 ran second
still runs second here, and its write is the one that stands.

THE REFUSALS (every one names what it is about):
  L1  a clip whose donor is not the final game. This decodes the final game's object layout
      format and Obj03 id only; the prototype's are not decoded here.
  L2  a line whose extent leaves its clip's source rectangle: it would switch the player over
      ground that is not this zone's (another paste, a corridor or the void).
  L4  a row outside the act, or a coordinate that the runtime's signed word compares or the
      sentinels could not order.
  L5  the donor's object layout, object table or Obj03 length table no longer reads the way
      this file expects.
(There is no L3. An overlap between two lines is legal Sonic 2 content, ordered as above.)
"""
import os
import re
import struct

import s2_donor
from layer_lines import (LayerLineError, engine_constants, rows,  # noqa: F401 (re-exported)
                         rows_text)


# ---------------------------------------------------------------------------
# Reading Obj03 out of the donor
# ---------------------------------------------------------------------------

def _s2_asm(donor):
    with open(os.path.join(s2_donor.donor_root(donor), "s2.asm")) as fh:
        return fh.read()


def obj03_id(asm):
    """Obj03's object id: its row's position in `Obj_Index`, which starts at id 1."""
    lines = asm.split("\n")
    try:
        start = next(i for i, ln in enumerate(lines) if ln.startswith("Obj_Index:"))
    except StopIteration:
        raise LayerLineError("L5 s2.asm has no `Obj_Index:` object pointer table") from None
    oid = 0
    for ln in lines[start + 1:]:
        m = re.match(r"^(ObjPtr_\w+):\s*dc\.l\s+(\w+)", ln)
        if not m:
            continue
        oid += 1
        if m.group(2) == "Obj03":
            if m.group(1) != "ObjPtr_PlaneSwitcher":
                raise LayerLineError(f"L5 s2.asm names Obj03's pointer {m.group(1)}, "
                                     f"not ObjPtr_PlaneSwitcher")
            return oid
        if oid > 0xFF:
            break
    raise LayerLineError("L5 s2.asm's Obj_Index has no Obj03 row")


def obj03_half_lengths(asm):
    """Obj03's four half-lengths, indexed by subtype bits 1:0, from the table Obj03_Init reads
    (`word_1FD68`, the four `dc.w` rows straight after the label)."""
    m = re.search(r"^word_1FD68:[^\n]*\n((?:[ \t]*dc\.w[ \t]+\$[0-9A-Fa-f]+[^\n]*\n){4})",
                  asm, re.M)
    if not m:
        raise LayerLineError("L5 s2.asm has no four-row `word_1FD68:` (Obj03's line lengths)")
    vals = [int(v, 16) for v in re.findall(r"dc\.w\s+\$([0-9A-Fa-f]+)", m.group(1))]
    if len(vals) != 4:
        raise LayerLineError(f"L5 word_1FD68 reads {vals}, not four hex words")
    return tuple(vals)


def object_layout_path(asm, donor, zone):
    """The zone's act-1 object layout, from its own `Objects_<layout>: BINCLUDE` line."""
    layout = s2_donor.zone_row(zone, donor)["layout"]
    found = re.findall(rf'^Objects_{layout}:\s*BINCLUDE\s+"([^"]+)"', asm, re.M)
    if len(found) != 1:
        raise LayerLineError(f"L5 s2.asm has {len(found)} `Objects_{layout}: BINCLUDE` lines, "
                             f"not one (a revision-conditional layout is not resolved here)")
    return os.path.join(s2_donor.donor_root(donor), found[0])


def read_layout(path):
    """[(x, y, x_flip, id, subtype)] — the final game's 6-byte object records (s2.asm
    ChkLoadObj: x word; y word with y in bits 11:0 and x-flip in bit 13; id; subtype). The file
    is records only: s2.asm brackets it with `ObjectLayoutBoundary` rather than terminating it,
    so a length that is not a whole number of records is a file this does not understand."""
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) % 6:
        raise LayerLineError(f"L5 {path}: {len(data)} bytes is not a whole number of 6-byte "
                             f"object records")
    out = []
    for i in range(0, len(data), 6):
        x, yw, oid, st = struct.unpack(">HHBB", data[i:i + 6])
        if x == 0xFFFF:
            break
        out.append((x, yw & 0x0FFF, (yw >> 13) & 1, oid, st))
    return out


# ---------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------

def flags_of(st, xflip, c):
    """Obj03's subtype + x-flip as the engine's ll_flags byte (see the module header)."""
    f = 0
    if xflip:
        f |= 1 << c["LL_KEEP_PATH"]
    if st & 0x80:
        f |= 1 << c["LL_GROUNDED"]
    if st & 0x04:
        f |= 1 << c["LL_HORIZONTAL"]
    if not xflip:
        if st & 0x08:
            f |= 1 << c["LL_FWD_B"]
        if st & 0x10:
            f |= 1 << c["LL_BACK_B"]
    if st & 0x20:
        f |= 1 << c["LL_FWD_HI"]
    if st & 0x40:
        f |= 1 << c["LL_BACK_HI"]
    return f


def lines(act, consts=None, asm_for=None):
    """Every Obj03 inside a clip's source rectangle, in ACT coordinates, one dict per LINE
    (before segmenting), in clip then layout order."""
    c = consts or engine_constants()
    asm_cache = {}
    out = []
    for cl in act.clips:
        if cl.donor != s2_donor.S2_FINAL:
            raise LayerLineError(
                f"L1 clip {cl.id!r} comes from donor {cl.donor!r}; its plane switchers cannot "
                f"be read (this decodes the final game's object layout and Obj03 id only)")
        if cl.donor not in asm_cache:
            asm_cache[cl.donor] = (asm_for or _s2_asm)(cl.donor)
        asm = asm_cache[cl.donor]
        oid, halves = obj03_id(asm), obj03_half_lengths(asm)
        path = object_layout_path(asm, cl.donor, cl.zone)
        sx, sy, sw, sh = cl.src
        dx, dy = cl.dst[0] - sx, cl.dst[1] - sy
        for x, y, xflip, o, st in read_layout(path):
            if o != oid or not (sx <= x < sx + sw and sy <= y < sy + sh):
                continue
            horiz = bool(st & 0x04)
            half = halves[st & 3]
            centre = x if horiz else y
            lo, hi = centre - half, centre + half
            where = f"{cl.zone} Obj03 at ({x}, {y}) subtype ${st:02X}"
            a0, a1 = (sx, sx + sw) if horiz else (sy, sy + sh)
            if lo < a0 or hi > a1:
                raise LayerLineError(
                    f"L2 {where}: its {'x' if horiz else 'y'} extent {lo}..{hi - 1} leaves "
                    f"clip {cl.id!r}'s source rectangle ({a0}..{a1 - 1}), so it would switch "
                    f"the player over ground that is not this zone's. Crop the clip differently.")
            shift = dx if horiz else dy
            out.append({"order": len(out), "zone": cl.zone, "clip": cl.id, "src": (x, y),
                        "subtype": st, "xflip": xflip, "horizontal": horiz, "half": half,
                        "x": x + dx, "y": y + dy, "lo": lo + shift, "hi": hi + shift,
                        "flags": flags_of(st, xflip, c), "where": where})
    return out


def plan(act, consts=None, asm_for=None):
    """{"lines": [...], "rows": [...], "consts": {...}} for a clip act (rows sorted, no
    sentinels)."""
    c = consts or engine_constants()
    ls = lines(act, c, asm_for)
    sec = act.section_px
    return {"lines": ls, "rows": rows(ls, act.grid_w * sec, act.grid_h * sec, c), "consts": c}


if __name__ == "__main__":
    import sys
    import clip_manifest
    p = plan(clip_manifest.load(sys.argv[1]))
    c = p["consts"]
    print(f"{len(p['lines'])} lines -> {len(p['rows'])} rows")
    for r in p["rows"]:
        kind = "H" if r["flags"] & (1 << c["LL_HORIZONTAL"]) else "V"
        print(f"  {kind} key {r['key']:5d} a {r['a']:5d} b {r['b']:5d} flags ${r['flags']:02X}  "
              f"{r['why']}")
