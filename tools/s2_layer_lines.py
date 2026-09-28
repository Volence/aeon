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

WHICH OBJECT LAYOUT (2026-09-27, woven HPZ/WFZ prep). The layout is the one the donor's own
object-pointer table names for the zone's act 1, never a name built from the level layout's:
  * FINAL (s2disasm): `Off_Objects`' act-1 row under the zone's comment row, then that label's
    `BINCLUDE`, with `if gameRevision=N` / `else` / `endif` resolved against s2.asm's own
    `gameRevision = N` (REV01). Wing Fortress is why: its level layout is `WFZ.kos` but its
    object layout is `Objects_WFZ_1`, and that label is BINCLUDEd twice, once per revision.
  * PROTOTYPE (s2-simonwai-disasm, Hidden Palace's only donor): `Objects_Layout`'s row
    `zone_id * 2` (zoneOrderedOffsetTable 2,2; the index ObjectsManager_Init computes from
    Current_ZoneAndAct), then that label's `binclude`. The prototype's record differs from the
    final game's in two places, both read off its own loader (main.asm `loc_E6C2`): x-flip is
    y-word bit 14 (`rol.w #2` then render flag bit 0), and the id byte's bit 7 is the
    remember-state flag (`andi.b #$7F`). Obj03's id is its row in the prototype's `objptr` list.

THE REFUSALS (every one names what it is about):
  L1  a clip whose donor is not a registered Sonic 2 donor.
  L2  a line whose extent leaves its clip's source rectangle: it would switch the player over
      ground that is not this zone's (another paste, a corridor or the void).
  L4  a row outside the act, or a coordinate that the runtime's signed word compares or the
      sentinels could not order.
  L5  the donor's object layout, object table or Obj03 length table no longer reads the way
      this file expects.
  L6  a PROTOTYPE Obj03 inside a clip. The prototype's Obj03 (obj/03 Collision Switcher.asm)
      is not the final game's rule that Player_LayerLines runs: it arms while the player is
      inside a 16-px band around the line and fires when he LEAVES the band, in any direction
      (out of either end too), on the side of x he is on; the final game fires on a crossing
      of the line within its extent, remembered per side. Baking it as the final rule would
      switch paths where the prototype does not, so it is refused rather than approximated.
      MEASURED 2026-09-27: Hidden Palace's act-1 layout carries NO Obj03 (43 records), so an
      HPZ clip bakes with zero lines, which is exactly the prototype's behaviour.
  L7  a corridor's declared path line (clip_manifest PATH LINES, `connector_lines`) whose
      donor premise does not hold: no such Obj03, a keep-path or horizontal one, one inside
      the crop or on the wrong side of it, one whose extent misses the corridor's standing
      height, or one with another path-setting line between it and the crop edge.
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
    """The donor's top-level assembly source: s2.asm (final) or main.asm (prototype)."""
    name = "s2.asm" if donor == s2_donor.S2_FINAL else "main.asm"
    with open(os.path.join(s2_donor.donor_root(donor), name), errors="replace") as fh:
        return fh.read()


def obj03_id(asm, donor=s2_donor.S2_FINAL):
    """Obj03's object id: its row's position in `Obj_Index`, which starts at id 1. The final
    game spells a row `ObjPtr_X: dc.l ObjNN`; the prototype `id_ObjNN: objptr ObjNN`, whose
    macro assigns ((* - Obj_Index) / 4) + 1, the same count."""
    lines = asm.split("\n")
    try:
        start = next(i for i, ln in enumerate(lines) if ln.startswith("Obj_Index:"))
    except StopIteration:
        raise LayerLineError("L5 the donor has no `Obj_Index:` object pointer table") from None
    row = (r"^(ObjPtr_\w+):\s*dc\.l\s+(\w+)" if donor == s2_donor.S2_FINAL
           else r"^(id_\w+):\s*objptr\s+(\w+)")
    oid = 0
    for ln in lines[start + 1:]:
        m = re.match(row, ln)
        if not m:
            continue
        oid += 1
        if m.group(2) == "Obj03":
            want = "ObjPtr_PlaneSwitcher" if donor == s2_donor.S2_FINAL else "id_Obj03"
            if m.group(1) != want:
                raise LayerLineError(f"L5 {donor} names Obj03's pointer {m.group(1)}, "
                                     f"not {want}")
            return oid
        if oid > 0xFF:
            break
    raise LayerLineError(f"L5 {donor}'s Obj_Index has no Obj03 row")


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


def _game_revision(asm):
    m = re.search(r"^gameRevision\s*=\s*(\d+)", asm, re.M)
    if not m:
        raise LayerLineError("L5 s2.asm declares no `gameRevision = N`, so a revision-"
                             "conditional object layout cannot be resolved")
    return int(m.group(1))


def _active_binclude(asm, label, start, rev):
    """The one path `<label>: BINCLUDE "..."` assembles to, walking s2.asm's conditionals from
    `start`: `if gameRevision=N` / `elseif gameRevision=N` / `else` / `endif` are evaluated
    against `rev`; a BINCLUDE of this label under any OTHER condition is refused (L5), never
    guessed."""
    lines = asm[start:].split("\n")
    stack = []                          # [(kind, taken_so_far, active)]
    found = []
    for ln in lines:
        s = ln.split(";", 1)[0].strip()
        low = s.lower()
        m = re.match(r"^(if|elseif)\s+gamerevision\s*=\s*(\d+)$", low)
        if m and m.group(1) == "if":
            hit = int(m.group(2)) == rev
            stack.append(["rev", hit, hit])
            continue
        if m:
            if not stack or stack[-1][0] != "rev":
                raise LayerLineError("L5 an `elseif gameRevision` outside a revision `if`")
            hit = not stack[-1][1] and int(m.group(2)) == rev
            stack[-1][1] |= hit
            stack[-1][2] = hit
            continue
        if re.match(r"^(if|ifdef|ifndef|ifeq|ifne)\b", low):
            stack.append(["other", False, None])
            continue
        if low == "else":
            if not stack:
                raise LayerLineError("L5 an `else` with no open conditional")
            if stack[-1][0] == "rev":
                stack[-1][2] = not stack[-1][1]
                stack[-1][1] = True
            continue
        if low == "endif":
            if not stack:
                break                   # left the conditional block this walk started in
            stack.pop()
            continue
        m = re.match(rf'^{re.escape(label)}:\s*binclude\s+"([^"]+)"', s, re.I)
        if m:
            if any(k == "other" for k, _t, _a in stack):
                raise LayerLineError(f"L5 `{label}` is BINCLUDEd under a condition that is not "
                                     f"gameRevision; not resolved here")
            if all(a for _k, _t, a in stack):
                found.append(m.group(1))
    if len(found) != 1:
        raise LayerLineError(f"L5 `{label}` assembles to {len(found)} BINCLUDE(s) at "
                             f"gameRevision {rev}, not one")
    return found[0]


def object_layout_path(asm, donor, zone):
    """The zone's act-1 object layout, through the donor's own object-pointer table (see the
    module header, WHICH OBJECT LAYOUT)."""
    root = s2_donor.donor_root(donor)
    if donor == s2_donor.S2_FINAL:
        m = re.search(r"^Off_Objects:.*?\n(.*?)^\s*zoneTableEnd", asm, re.M | re.S)
        if not m:
            raise LayerLineError("L5 s2.asm has no `Off_Objects:` table")
        rows = m.group(1).split("\n")
        at = next((i for i, ln in enumerate(rows)
                   if re.match(rf"^\s*;\s*{re.escape(zone)}\s*$", ln)), None)
        if at is None:
            raise LayerLineError(f"L5 Off_Objects has no `; {zone}` row")
        m1 = re.match(r"^\s*zoneOffsetTableEntry\.w\s+(\w+)\s*;\s*Act 1\b", rows[at + 1])
        if not m1:
            raise LayerLineError(f"L5 Off_Objects' row after `; {zone}` is not its Act 1 entry")
        rel = _active_binclude(asm, m1.group(1), m.end(), _game_revision(asm))
        return os.path.join(root, rel)
    zid = s2_donor.zone_row(zone, donor)["zone_id"]
    m = re.search(r"^Objects_Layout:\s*zoneOrderedOffsetTable\s+2,\s*2\s*\n(.*?)^\s*zoneTableEnd",
                  asm, re.M | re.S)
    if not m:
        raise LayerLineError("L5 the prototype has no `Objects_Layout: zoneOrderedOffsetTable 2,2`")
    labels = re.findall(r"^\s*zoneOffsetTableEntry\.w\s+(\w+)", m.group(1), re.M)
    if len(labels) <= zid * 2:
        raise LayerLineError(f"L5 Objects_Layout has {len(labels)} rows; zone ${zid:02X} act 1 "
                             f"is row {zid * 2}")
    label = labels[zid * 2]
    found = re.findall(rf'^{re.escape(label)}:\s*binclude\s+"([^"]+)"', asm, re.M | re.I)
    if len(found) != 1:
        raise LayerLineError(f"L5 the prototype has {len(found)} `{label}: binclude` lines, "
                             f"not one")
    return os.path.join(root, found[0])


def read_layout(path, donor=s2_donor.S2_FINAL):
    """[(x, y, x_flip, id, subtype)] — the donor's 6-byte object records: x word; y word with y
    in bits 11:0 and x-flip in bit 13 (final, s2.asm ChkLoadObj) or bit 14 (prototype,
    main.asm loc_E6C2: `rol.w #2` into render flag bit 0); id (the prototype's bit 7 is the
    remember-state flag, masked off as its loader does); subtype. The file is records only:
    both donors bracket it with `ObjectLayoutBoundary` rather than terminating it, so a length
    that is not a whole number of records is a file this does not understand."""
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) % 6:
        raise LayerLineError(f"L5 {path}: {len(data)} bytes is not a whole number of 6-byte "
                             f"object records")
    final = donor == s2_donor.S2_FINAL
    out = []
    for i in range(0, len(data), 6):
        x, yw, oid, st = struct.unpack(">HHBB", data[i:i + 6])
        if x == 0xFFFF:
            break
        out.append((x, yw & 0x0FFF, (yw >> (13 if final else 14)) & 1,
                    oid if final else oid & 0x7F, st))
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
        if cl.donor not in s2_donor.DONORS:
            raise LayerLineError(
                f"L1 clip {cl.id!r} comes from donor {cl.donor!r}, which is not a registered "
                f"Sonic 2 donor; its plane switchers cannot be read")
        if cl.donor not in asm_cache:
            asm_cache[cl.donor] = (asm_for or _s2_asm)(cl.donor)
        asm = asm_cache[cl.donor]
        oid = obj03_id(asm, cl.donor)
        path = object_layout_path(asm, cl.donor, cl.zone)
        sx, sy, sw, sh = cl.src
        dx, dy = cl.dst[0] - sx, cl.dst[1] - sy
        inside = [r for r in read_layout(path, cl.donor)
                  if r[3] == oid and sx <= r[0] < sx + sw and sy <= r[1] < sy + sh]
        if cl.donor != s2_donor.S2_FINAL:
            if inside:
                x, y, _f, _o, st = inside[0]
                raise LayerLineError(
                    f"L6 {cl.zone} ({cl.donor}) Obj03 at ({x}, {y}) subtype ${st:02X} is inside "
                    f"clip {cl.id!r}: the prototype's Obj03 fires on LEAVING a 16-px band, not "
                    f"on crossing the line, and the engine runs only the final game's rule "
                    f"({len(inside)} such line(s) in the rectangle)")
            continue
        halves = obj03_half_lengths(asm)
        for x, y, xflip, o, st in inside:
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


#: How far inside the corridor, before the mouth it serves, a path line is placed (px). A step
#: of up to LL_STEP_MAX_X (16 px, player_common.emp) crosses it, and the frame after, every
#: sensor (the widest reach is a wall sensor's ~10 px plus that step) still reads corridor
#: cells, which are identical on both planes: so the path is set before any sensor can read
#: the arrival clip's collision on the old one. Two collision blocks.
PATH_LINE_INSET_PX = 32


def connector_lines(act, consts=None, asm_for=None, order0=0):
    """The declared `path_lines` of the act's corridors (clip_manifest PATH LINES, K11), one
    LINE record each: a copy of the named donor Obj03, placed PATH_LINE_INSET_PX inside the
    corridor before the mouth it serves and spanning the corridor's open height, with the
    Obj03's own subtype re-packed. Each is refused (L7) unless the premise the declaration
    rests on holds in the donor:
      * the clip at that mouth is a FINAL-game clip (the prototype's rule is L6's refusal);
      * exactly one Obj03 of the zone's act-1 layout sits at the named donor (x, y);
      * it SETS a path (not x-flipped) and is vertical (a corridor is crossed along x);
      * it lies OUTSIDE the crop, on the corridor's side (west of the crop for the east mouth,
        east of it for the west mouth): inside, it is already baked by `lines()`;
      * its extent covers the body of a player standing on the corridor floor, mapped into
        donor coordinates ([floor_y - 2 x PLAYER_Y_RADIUS, floor_y)): the height a run
        through the corridor arrives at;
      * no OTHER path-setting vertical Obj03 of the zone whose extent meets that band lies
        between it and the crop edge: it is the last path Sonic 2 sets on that run.
    That premise is the nearest-line estimate WOVEN-CROSSING-PATH measured wrong elsewhere, so
    it is necessary only; what admits a declaration is the witness (see the header of
    clip_manifest PATH LINES). The records carry `mouth`, `connector` and `subtype`, which
    tools/path_b_floor_witness.py --connectors grades the arrival path against."""
    import clip_manifest as CM
    c = consts or engine_constants()
    radius2 = CM.player_clearance_px() - 1          # 2 x PLAYER_Y_RADIUS
    asm_cache = {}
    out = []
    for co in getattr(act, "corridors", ()):
        if not getattr(co, "path_lines", None):
            continue
        _ax, west_clip, east_clip = CM.connector_ends(act, co)
        for pl in co.path_lines:
            cl = east_clip if pl["mouth"] == "east" else west_clip
            ox, oy = pl["donor_obj03"]
            where = (f"corridor {co.id!r} {pl['mouth']} mouth: {cl.zone if cl else '?'} Obj03 "
                     f"at ({ox}, {oy})")
            if cl is None:
                raise LayerLineError(f"L7 {where}: no clip meets that mouth")
            if cl.donor != s2_donor.S2_FINAL:
                raise LayerLineError(f"L7 {where}: clip {cl.id!r} is a {cl.donor} clip; only "
                                     f"the final game's Obj03 rule is run (L6's reason)")
            if cl.donor not in asm_cache:
                asm_cache[cl.donor] = (asm_for or _s2_asm)(cl.donor)
            asm = asm_cache[cl.donor]
            oid = obj03_id(asm, cl.donor)
            halves = obj03_half_lengths(asm)
            recs = [r for r in read_layout(object_layout_path(asm, cl.donor, cl.zone), cl.donor)
                    if r[3] == oid]
            hit = [r for r in recs if (r[0], r[1]) == (ox, oy)]
            if len(hit) != 1:
                raise LayerLineError(f"L7 {where}: {len(hit)} Obj03 record(s) there in the "
                                     f"zone's act-1 layout, not one")
            _x, _y, xflip, _o, st = hit[0]
            if xflip:
                raise LayerLineError(f"L7 {where} subtype ${st:02X} is x-flipped: it keeps the "
                                     f"path, so it cannot be the line that sets it")
            if st & 0x04:
                raise LayerLineError(f"L7 {where} subtype ${st:02X} is horizontal; a corridor "
                                     f"is crossed along x")
            sx, sy, sw, _sh = cl.src
            dy = cl.dst[1] - sy
            if pl["mouth"] == "east" and not ox < sx:
                raise LayerLineError(f"L7 {where}: x {ox} is not west of clip {cl.id!r}'s crop "
                                     f"(src x {sx}); a line inside the crop is baked already")
            if pl["mouth"] == "west" and not ox >= sx + sw:
                raise LayerLineError(f"L7 {where}: x {ox} is not east of clip {cl.id!r}'s crop "
                                     f"(src x ..{sx + sw - 1}); a line inside the crop is "
                                     f"baked already")
            b0, b1 = co.floor_y - radius2 - dy, co.floor_y - dy
            half = halves[st & 3]
            if not (oy - half <= b0 and b1 <= oy + half):
                raise LayerLineError(
                    f"L7 {where} subtype ${st:02X}: its extent y {oy - half}..{oy + half - 1} "
                    f"does not cover the standing body on the corridor floor, donor y "
                    f"{b0}..{b1 - 1}")
            lo_x, hi_x = (ox, sx) if pl["mouth"] == "east" else (sx + sw - 1, ox)
            between = [r for r in recs
                       if lo_x < r[0] < hi_x and not r[2] and not r[4] & 0x04
                       and r[1] - halves[r[4] & 3] < b1 and b0 < r[1] + halves[r[4] & 3]]
            if between:
                x2, y2, _f, _o, st2 = between[0]
                raise LayerLineError(
                    f"L7 {where}: the path-setting Obj03 at ({x2}, {y2}) subtype ${st2:02X} "
                    f"lies between it and the crop edge across the same band, so it is not the "
                    f"last path Sonic 2 sets on that run")
            top = co.tunnel.ceiling_y if co.tunnel is not None else co.dst[1]
            x = (co.dst[0] + co.dst[2] - PATH_LINE_INSET_PX if pl["mouth"] == "east"
                 else co.dst[0] + PATH_LINE_INSET_PX)
            out.append({"order": order0 + len(out), "zone": "connector", "clip": co.id,
                        "connector": co.id, "mouth": pl["mouth"], "src": (ox, oy),
                        "donor_zone": cl.zone, "subtype": st, "xflip": 0, "horizontal": False,
                        "half": (co.floor_y - top) // 2, "x": x, "y": top, "lo": top,
                        "hi": co.floor_y, "flags": flags_of(st, 0, c),
                        "where": f"{where} subtype ${st:02X} (path line)"})
    return out


def plan(act, consts=None, asm_for=None):
    """{"lines": [...], "rows": [...], "consts": {...}} for a clip act (rows sorted, no
    sentinels): every Obj03 inside a clip (`lines`), then every declared corridor path line
    (`connector_lines`)."""
    c = consts or engine_constants()
    ls = lines(act, c, asm_for)
    ls += connector_lines(act, c, asm_for, order0=len(ls))
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
