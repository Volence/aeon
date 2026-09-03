#!/usr/bin/env python3
"""canopy_record — read the canopy-gap capture instrument's latch out of a DEBUG machine.

WHAT THE INSTRUMENT IS. `engine/level/section.emp` (Canopy_Probe / Canopy_Fire /
Canopy_Persist) plus two shadow writes in `engine/level/plane_buffer.emp` record, for every
plane column and every plane row, WHICH WORLD CELL its last writer put there and WHEN.
Two predicates fire off that shadow:

    C1  a visible plane COLUMN does not hold the world column the camera says it holds
        (or holds $FFFF -- nothing has written it since the last full redraw). Latched only
        after CANOPY_PERSIST_FRAMES consecutive sweeps on the same plane column.
    C4  a row write was about to impose an anchor R that does not cover the visible
        columns, caught at the write's own site.

THIS TOOL DOES NOT DIAGNOSE, and that is deliberate: the canopy gap has already outlived
two derived explanations (`docs/DEFERRED_WORK.md`, "CANOPY GAP"), both refuted by
measurement. What it prints is the record, decoded, plus the three arithmetic facts a
reader needs to place it -- which columns disagree, by how many wrap-twins, and whether the
trackers claimed more than any writer reached. The conclusion is the reader's.

WHY A SHADOW AT ALL, since this is the question everyone asks first: which world cell a
plane cell holds cannot be recovered from VRAM. The act tileset is globally deduplicated,
so one tile word legitimately belongs to many world cells and plane A carries no
provenance. Only the writer knows, and only while it writes.

USAGE
    python3 tools/canopy_record.py                       # read the running machine
    python3 tools/canopy_record.py --arm                 # set Canopy_Halt: stop on next fire
    python3 tools/canopy_record.py --disarm
    python3 tools/canopy_record.py --save capture.json   # archive the raw record
    python3 tools/canopy_record.py --dump capture.json   # re-read an archive, no emulator

Exit codes (the house contract): 0 the record was read (fired or not), 1 never used --
this is a reader, not a gate, and it has no verdict to fail on, 2 setup /
could-not-measure.

RUN IT FOREGROUND when it talks to a machine: it uses `tools/aether_instance.py`, and
oracle from a background agent deadlocks. `--dump` needs no machine and is safe anywhere.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(AEON, "tools"))


class SetupError(Exception):
    """The record could not be read. Exit 2 -- never a verdict."""


# The scalar record, in the order the report prints it. Names are resolved from the
# listing, never from an offset: a RAM layout change must move the read, not silently
# shift it onto the next field.
SCALARS = [
    "Canopy_Rec_Code", "Canopy_Rec_Frame", "Canopy_Rec_Idx", "Canopy_Rec_Want",
    "Canopy_Rec_Got", "Canopy_Rec_Stamp",
    "Canopy_Rec_SecR", "Canopy_Rec_SecL", "Canopy_Rec_SecB", "Canopy_Rec_SecT",
    "Canopy_Rec_CacheHead", "Canopy_Rec_CacheLeft", "Canopy_Rec_CacheTop",
    "Canopy_Rec_CacheBot", "Canopy_Rec_OrgCol", "Canopy_Rec_OrgRow",
    "Canopy_Rec_ResumeCol", "Canopy_Rec_ResumeRow", "Canopy_Rec_PBPtr",
    "Canopy_Rec_Stall", "Canopy_Rec_RedrawFr", "Canopy_Rec_RedrawL", "Canopy_Rec_RedrawR",
    "Canopy_Pend_Code", "Canopy_Pend_Idx", "Canopy_Pend_Age",
    "Canopy_Halt", "Canopy_Cost", "Canopy_Cost_Peak",
    "Canopy_Redraw_Fr", "Canopy_Redraw_L", "Canopy_Redraw_R",
]
LONGS = ["Canopy_Rec_CamX", "Canopy_Rec_CamY"]
ARRAYS = ["Canopy_Hits", "Canopy_First_Fr"]                       # 4 words each
SNAPS = ["Canopy_Snap_ColW", "Canopy_Snap_ColTop", "Canopy_Snap_ColFrame",
         "Canopy_Snap_RowR", "Canopy_Snap_RowFrame"]              # PLANE cells each
LIVE = ["Canopy_ColW", "Canopy_ColTop", "Canopy_ColFrame", "Canopy_RowR", "Canopy_RowFrame"]

CODE_NAMES = {0: "(empty -- the instrument has never latched)",
              1: "C1  a visible plane COLUMN holds the wrong world column",
              4: "C4  a row write imposed an anchor that missed the visible columns"}

NEVER = 0xFFFF


def words(buf: bytes) -> list[int]:
    return [(buf[i] << 8) | buf[i + 1] for i in range(0, len(buf), 2)]


# ---- the decoder: bytes in, report out. No emulator, no I/O, unit-tested. ----

def decode(rec: dict, plane_h: int, plane_v: int, last_col: int, last_row: int,
           persist_frames: int) -> list[str]:
    """Render one capture. `rec` maps every name above to an int (scalars/longs) or a
    list of ints (arrays/snaps/live). Geometry comes from the caller, which parses it out
    of `engine/system/constants.emp` -- nothing here is pinned.
    """
    out: list[str] = []
    code = rec["Canopy_Rec_Code"]
    hits = rec["Canopy_Hits"]
    firstfr = rec["Canopy_First_Fr"]

    out.append("canopy_record:")
    out.append(f"  fires: C1 {hits[0]}  C4 {hits[3]}"
               f"   (first at frame: C1 {firstfr[0]}, C4 {firstfr[3]})")
    out.append(f"  sweep self-price: {rec['Canopy_Cost']} scanlines last, "
               f"{rec['Canopy_Cost_Peak']} peak")
    out.append(f"  halt arm: {'ARMED (raise_error on the next fire)' if rec['Canopy_Halt'] else 'off (latch silently)'}")
    if rec["Canopy_Pend_Code"]:
        out.append(f"  C1 pending right now: plane column {rec['Canopy_Pend_Idx']}, "
                   f"age {rec['Canopy_Pend_Age']}/{persist_frames} sweeps")

    if code == 0:
        out.append("")
        out.append("  NOTHING IS LATCHED. Read that as exactly one of:")
        out.append("    * no disagreement of either shape has occurred since boot; or")
        out.append("    * a disagreement occurred that neither predicate describes.")
        out.append("  It is NOT evidence that the canopy gap is fixed, and it is not")
        out.append("  evidence that it is not: a sighting was already rare before this")
        out.append("  instrument existed. If the owner SAW a gap and this is empty, that")
        out.append("  is the most informative outcome available and it means the cause is")
        out.append("  outside plane-A cell addressing entirely -- see WHAT THIS MISSES in")
        out.append("  the parcel report.")
        return out

    cam_x, cam_y = rec["Canopy_Rec_CamX"], rec["Canopy_Rec_CamY"]
    cam_col, cam_row = (cam_x >> 16) >> 3, (cam_y >> 16) >> 3
    out.append("")
    out.append(f"  LATCHED: {CODE_NAMES.get(code, f'unknown code {code}')}")
    out.append(f"    at frame {rec['Canopy_Rec_Frame']}, camera "
               f"({cam_x >> 16}, {cam_y >> 16}) px = world cell ({cam_col}, {cam_row})")
    out.append(f"    visible world columns {cam_col}..{cam_col + last_col}, "
               f"rows {cam_row}..{cam_row + last_row}")

    idx, want, got = rec["Canopy_Rec_Idx"], rec["Canopy_Rec_Want"], rec["Canopy_Rec_Got"]
    if code == 1:
        out.append(f"    plane column {idx}: wanted world column {want}, "
                   f"{'NEVER WRITTEN ($FFFF)' if got == NEVER else f'holds {got}'}")
        if got != NEVER:
            d = want - got
            twins = d / plane_h
            out.append(f"      difference {d:+d} = {twins:+g} wrap twins of {plane_h} "
                       f"columns ({abs(d) * 8} px)")
            if d % plane_h:
                out.append("      NOT a whole multiple of the ring width. Every column "
                           "write puts W at plane column W & 63, so this cannot come "
                           "from a column write at all -- read it as a corrupted shadow "
                           "or a writer nobody has accounted for, and say so.")
        out.append(f"      written by frame {rec['Canopy_Rec_Stamp']} "
                   f"(0 = never since the last full redraw)")
    else:
        out.append(f"    plane row {idx}, world row {want}: the write imposed anchor "
                   f"R = {got}")
        out.append(f"      it needed {cam_col + last_col} <= R <= {cam_col + plane_h - 1}; "
                   f"R is {'SHORT of the screen right edge by %d' % (cam_col + last_col - got) if got < cam_col + last_col else 'PAST camCol+%d by %d' % (plane_h - 1, got - cam_col - plane_h + 1)}")

    out.append("")
    out.append("  trackers and cache window at the fire:")
    out.append(f"    Section_Written  L {rec['Canopy_Rec_SecL']}  R {rec['Canopy_Rec_SecR']}"
               f"   T {rec['Canopy_Rec_SecT']}  B {rec['Canopy_Rec_SecB']}")
    out.append(f"    Cache            L {rec['Canopy_Rec_CacheLeft']}  H {rec['Canopy_Rec_CacheHead']}"
               f"   T {rec['Canopy_Rec_CacheTop']}  B {rec['Canopy_Rec_CacheBot']}"
               f"   origin ({rec['Canopy_Rec_OrgCol']}, {rec['Canopy_Rec_OrgRow']})")
    rc, rr = rec["Canopy_Rec_ResumeCol"], rec["Canopy_Rec_ResumeRow"]
    out.append(f"    fill partial     col {'none' if rc == NEVER else rc}   "
               f"row {'none' if rr == NEVER else rr}")
    out.append(f"    Plane_Buffer_Ptr {rec['Canopy_Rec_PBPtr']}   Cache_Art_Stall {rec['Canopy_Rec_Stall']}")
    out.append(f"    last redraw      frame {rec['Canopy_Rec_RedrawFr']}, returned "
               f"L {rec['Canopy_Rec_RedrawL']} R {rec['Canopy_Rec_RedrawR']}")

    # -- the three arithmetic facts, computed rather than asserted --
    colw = rec["Canopy_Snap_ColW"]
    colfr = rec["Canopy_Snap_ColFrame"]
    rowfr = rec["Canopy_Snap_RowFrame"]
    rowr = rec["Canopy_Snap_RowR"]

    vis = [(cam_col + i) for i in range(last_col + 1)]
    wrong = [(w, colw[w % plane_h]) for w in vis if colw[w % plane_h] != w]
    out.append("")
    out.append(f"  FACT 1 -- visible plane columns whose shadow disagrees: "
               f"{len(wrong)} of {last_col + 1}")
    if wrong:
        runs, start, prev = [], wrong[0][0], wrong[0][0]
        for w, _ in wrong[1:]:
            if w == prev + 1:
                prev = w
            else:
                runs.append((start, prev)); start = prev = w
        runs.append((start, prev))
        out.append("    world-column runs: " +
                   ", ".join(f"{a}..{b}" if a != b else str(a) for a, b in runs))
        out.append("    a single run at the LEADING edge is a streamer that fell behind;")
        out.append("    a run in the MIDDLE of the screen is not, and is the interesting shape.")

    written = [c for c in colw if c != NEVER]
    out.append("")
    if written:
        lo, hi = min(written), max(written)
        secr = rec["Canopy_Rec_SecR"]
        over = secr - hi
        out.append(f"  FACT 2 -- the extent any column writer actually reached: {lo}..{hi}")
        out.append(f"    Section_Right_Col_Written claimed {secr}: "
                   + (f"OVER-CLAIMS BY {over} column(s)" if over > 0 else "within it"))
        out.append(f"    the last redraw returned R = {rec['Canopy_Rec_RedrawR']} at frame "
                   f"{rec['Canopy_Rec_RedrawFr']}")
        out.append("    an over-claim whose size matches the redraw's R is the shape of a")
        out.append("    tracker written from a redraw that did not draw that far. It is a")
        out.append("    shape, not a proof: check the frame numbers before believing it.")
    else:
        out.append("  FACT 2 -- NO plane column has ever been written. That is not a "
                   "canopy gap, it is a machine that never drew the level.")

    vr = [(cam_row + i) for i in range(last_row + 1)]
    owned = [q for q in vr if rowr[q % plane_v] != NEVER]
    out.append("")
    out.append(f"  FACT 3 -- visible plane rows a row write owns: {len(owned)} of {len(vr)}")
    if owned:
        anchors = sorted({rowr[q % plane_v] for q in owned})
        out.append(f"    distinct anchors in play: {anchors}")
        out.append(f"    the window each imposes must contain {cam_col}..{cam_col + last_col}")
    out.append(f"    oldest visible row-write stamp: "
               f"{min(rowfr[q % plane_v] for q in vr)}; "
               f"oldest visible column-write stamp: {min(colfr[w % plane_h] for w in vis)}")
    out.append("    a column stamp OLDER than every row stamp means every visible cell of")
    out.append("    that column was rewritten by row writes after it -- the column's own")
    out.append("    shadow is then stale without anything being wrong on screen.")
    return out


# ---- geometry, parsed from the engine's own constants ----

def geometry() -> dict:
    """PLANE_*_CELLS, SCREEN_LAST_*_MAX and CANOPY_PERSIST_FRAMES out of constants.emp.

    Parsed, never pinned: a gate that hardcodes a geometry constant is a gate measuring
    the wrong rectangle, and SCREEN_LAST_ROW_MAX's own source comment is off by one
    (`(7 + 224 - 1) >> 3` is 28, the comment says 27), which is exactly the class of
    mistake copying the number would import.
    """
    import re
    src = os.path.join(AEON, "engine/system/constants.emp")
    txt = open(src).read()
    env: dict[str, int] = {}

    def const(name: str) -> int:
        if name in env:
            return env[name]
        m = re.search(rf"^\s*pub\s+const\s+{re.escape(name)}\s*=\s*([^/\n]+)", txt, re.M)
        if not m:
            raise SetupError(f"cannot find `pub const {name}` in {src}")
        expr = m.group(1).strip()
        # the only forms these five constants are written in; anything else raises
        tok = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+|>>|[-+()]", expr)
        py = " ".join(str(const(t)) if re.match(r"^[A-Za-z_]", t) else t for t in tok)
        try:
            env[name] = int(eval(py, {"__builtins__": {}}, {}))  # noqa: S307 -- tokens are whitelisted above
        except Exception as exc:
            raise SetupError(f"cannot evaluate `{name} = {expr}` from {src}: {exc}") from exc
        return env[name]

    return {n: const(n) for n in ("PLANE_H_CELLS", "PLANE_V_CELLS",
                                 "SCREEN_LAST_COL_MAX", "SCREEN_LAST_ROW_MAX",
                                 "CANOPY_PERSIST_FRAMES")}


# ---- the machine front end ----

async def read_live(lst: str, rom: str, arm: int | None) -> dict:
    from suite_paths import add_client_path
    add_client_path()
    from aether_instance import AetherInstance
    from raster_cost_probe import parse_lst

    sym = parse_lst(lst)
    missing = [n for n in SCALARS + LONGS + ARRAYS + SNAPS + LIVE if n not in sym]
    if missing:
        raise SetupError(
            f"{lst} has no {missing[0]} (and {len(missing) - 1} more). The instrument is "
            f"DEBUG-only -- point --lst at s4.debug.lst, and make sure it is THIS build's.")

    rec: dict = {}
    async with AetherInstance(rom=rom) as inst:
        b = inst.bus

        async def rd(addr: int, n: int) -> bytes:
            r = await b.call("emulator/read_memory", {"addr": hex(addr), "len": n})
            h = str(r["bytes"]).removeprefix("0x").removeprefix("0X")
            if len(h) != 2 * n:
                raise SetupError(f"read_memory returned {len(h) // 2} bytes at {addr:#x}, wanted {n}")
            return bytes.fromhex(h)

        if arm is not None:
            await b.call("emulator/write_memory",
                         {"addr": hex(sym["Canopy_Halt"]), "bytes": "0x%04X" % arm})
        for n in SCALARS:
            rec[n] = words(await rd(sym[n], 2))[0]
        for n in LONGS:
            v = await rd(sym[n], 4)
            rec[n] = int.from_bytes(v, "big")
        for n in ARRAYS:
            rec[n] = words(await rd(sym[n], 8))
        g = geometry()
        for n in SNAPS + LIVE:
            cells = g["PLANE_V_CELLS"] if "Row" in n else g["PLANE_H_CELLS"]
            rec[n] = words(await rd(sym[n], cells * 2))
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(prog="canopy_record")
    ap.add_argument("--rom", default=os.path.join(AEON, "s4.debug.bin"))
    ap.add_argument("--lst", default=None, help="default: the ROM's own .lst")
    ap.add_argument("--dump", help="decode an archived record instead of a machine")
    ap.add_argument("--save", help="write the raw record to this JSON file as well")
    ap.add_argument("--arm", action="store_true",
                    help="set Canopy_Halt: the machine stops itself on the next fire")
    ap.add_argument("--disarm", action="store_true", help="clear Canopy_Halt")
    a = ap.parse_args()

    try:
        if a.dump:
            rec = json.load(open(a.dump))
            g = rec.pop("_geometry")
        else:
            import asyncio
            lst = a.lst or (a.rom[:-4] + ".lst")
            arm = 1 if a.arm else (0 if a.disarm else None)
            rec = asyncio.run(read_live(lst, a.rom, arm))
            g = geometry()
        if a.save:
            json.dump({**rec, "_geometry": g}, open(a.save, "w"), indent=1)
            print(f"canopy_record: wrote {a.save}")
        for line in decode(rec, g["PLANE_H_CELLS"], g["PLANE_V_CELLS"],
                           g["SCREEN_LAST_COL_MAX"], g["SCREEN_LAST_ROW_MAX"],
                           g["CANOPY_PERSIST_FRAMES"]):
            print(line)
    except SetupError as exc:
        print(f"canopy_record: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
