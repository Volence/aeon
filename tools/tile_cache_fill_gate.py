#!/usr/bin/env python3
"""tile_cache_fill_gate — a column the streamer RECORDS as written must actually be written.

WHAT IT GATES. `engine/level/section.emp`'s four streaming loops draw newly revealed plane
cells through `Draw_TileColumn` / `Draw_TileRow_FromCache` and then record how far they got
in `Section_{Left,Right}_Col_Written` / `Section_{Top,Bottom}_Row_Written`. Those four words
are a PROMISE: a cell inside them is never revisited until the 64-cell plane ring wraps onto
it, tens of seconds of travel later. So a cell that is recorded but was drawn from cache the
fill had not populated stays wrong on screen for as long as the player can see it. That is
the shape of the reported canopy gap: a narrow vertical strip that goes missing and STAYS
missing.

THE ASSERTION is therefore exactly the promise, read out of the running machine:

    for every cell inside the recorded window that is also on screen and inside the tile
    cache's own window:   plane A word  ==  tile cache word

Both sides come from the SAME sampled frame of the SAME machine. Nothing here is pinned: the
tested set is computed from the engine's own trackers and the cache's own window at the
sample point, and the geometry constants are parsed out of `engine/system/constants.emp`.

A SECOND, CHEAPER ASSERTION rides along, because it is the invariant in its own terms and it
needs no VRAM at all: the tile cache's pending PARTIAL fill — `Cache_Fill_Resume_Col` for the
column axis, `Cache_Fill_RowResume_Row` for the row axis, both $FFFF when there is none — must
never lie inside the recorded window. `Tile_Cache_Fill` commits `Cache_Head_Col` (and
`Cache_Left_Col`, `Cache_Bottom_Row`, `Cache_Top_Row`) BEFORE calling the fill for that
column/row, so a budget-out or a demand stall leaves the declared window advertising a
column the fill only partly wrote. If the streamer then draws and RECORDS it, the promise is
broken and assertion 1 will find the damage some frames later. Assertion 2 catches the same
defect at its source and names it.

THE RING. The tile cache is a RING on both axes. World column W lives at physical column
`(W - Cache_Left_Col + Cache_Origin_Col) mod TILE_CACHE_COLS`, and cache logical row L (world
row `Cache_Top_Row + L`) lives at physical row `(Cache_Origin_Row + L) mod TILE_CACHE_ROWS`.
Indexing it as a LINEAR window returns a plausible and entirely wrong answer — that mistake
produced two wrong readings during the investigation this gate came out of, and the second of
them is what the gate exists to make impossible to repeat. `--control` prints the neighbour
control that proves the indexing before any occupancy number is trusted.

WHAT IS EXCLUDED, and why the gate is worthless without the exclusions:

  * cells OUTSIDE the recorded window. Cache-has / VRAM-empty is NORMAL at the scroll's
    leading edge: the streamer has not drawn those columns yet, and it says so. Likewise the
    plane legitimately still holds the wrap twin's tiles 64 columns back there.
  * cells outside the cache window, and cells off screen.
  * the drain lag. `Draw_TileColumn` APPENDS to `Plane_Buffer`; `VInt_DrawLevel` drains it in
    the next VBlank, while `Section_Right_Col_Written` advances at game-loop time. A sample
    taken between the two sees the tracker ahead of the plane through no fault of the fill.
    MEASURED: sampling straight after a held-RIGHT burst produced one such false positive in
    150 samples (camX 4176, cols 561-562, 18 rows each). `--post` frames with the buttons
    released is the fix, and it is also the right sample point for the subject: a real hole is
    permanent and survives the settle, a drain lag does not.

POISON (what must make it red), and why it takes two edits. The starved regime this defect
lives in does NOT occur on OJZ act 1 at the shipped settings: `TILE_CACHE_COLS` (80) exceeds
`TILE_CACHE_MARGIN_H` (20) + the column fill's reach (41) by 19 columns, so the fill's
frontier — where the partial always sits — runs 19 columns ahead of anything the streamer
will draw, and the resume preamble closes it long before the camera arrives. That structural
slack is why a run on the shipped ROM is a green that has not been to the place, and why it
must not be mistaken for evidence on its own. Consume the slack:

    1. engine/system/constants.emp    pub const BLOCK_DECOMP_BUDGET = 1        (shipped: 6)
    2. engine/level/tile_cache.emp    TileCache_FillColumn, immediately before
                                      `jbsr TileCache_FindStagedBlock`, charge the budget
                                      for every block VISITED rather than only for a
                                      decompress:
                                          tst.w   Cache_Fill_Budget
                                          beq     .fc_budget_out
                                          subq.w  #1, Cache_Fill_Budget

    DEBUG=1 ./build.sh && python3 tools/tile_cache_fill_gate.py --samples 30

Edit 1 alone is not enough — the 16-slot staging cache absorbs it and the fill never
partials. Edit 2 alone is not enough either: it makes the fill partial on nearly every frame
(assertion 2's "partial outstanding at N of the sample points" counter goes to 24/25) but the
partial still sits beyond the streamer's reach and nothing is drawn wrong. Together the fill
falls behind far enough that the streamer's own right edge reaches the partial column, which
is the condition under test.

MEASURED on master before the fix (2026-08-29, s4.debug crc32 a17e3055): 14 violations in the
first 5 samples, including `INTERIOR HOLE (cache has tiles, plane A is empty)` at world
columns 85-91 — 2 to 3 rows each, inside the recorded window, and STILL WRONG two samples and
128 px of travel later. That is the reported symptom exactly. With the fix and the identical
poison: zero violations. Restore both edits afterwards; the shipped ROM must be green too,
which is the second half of the evidence and not a substitute for the first.

LOUD ON UNMEASURABLE. A server serving a different ROM, a symbol that will not resolve, a
camera that never moved, or a run in which NO sample ever had anything to compare — each is a
failure with its own message, never a zero and never a green. A SINGLE sample with nothing to
compare is counted and reported as a caveat rather than failed: under a hard-starved fill the
recorded window legitimately falls off the screen once the loops refuse to record what they
did not write, and that state proves nothing either way.

USAGE
    python3 tools/tile_cache_fill_gate.py                       # s4.debug.bin, 40 samples
    python3 tools/tile_cache_fill_gate.py --samples 80 --step 8
    python3 tools/tile_cache_fill_gate.py --control             # print the ring-index control
    python3 tools/tile_cache_fill_gate.py --rom s4.bin

Exit codes (the house contract): 0 pass, 1 an assertion failed, 2 setup / could-not-measure.

RUN IT FOREGROUND. It boots a headless emulator through `tools/aether_instance.py`; oracle
from a background agent deadlocks.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import zlib

AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/, for suite_paths
from suite_paths import add_client_path  # noqa: E402
add_client_path()  # the Aether client, resolved from the suite root; loud if absent
sys.path.insert(0, os.path.join(AEON, "tools"))

from aether import BusClient                     # noqa: E402
from aether_instance import AetherInstance        # noqa: E402
from raster_cost_probe import parse_lst           # noqa: E402

MAX_READ = 4096          # the server's limits.maxReadLen, for both read_memory and read_vram


class SetupError(Exception):
    """The measurement could not be made. Exit 2 — never a verdict."""


# ---- expectations, parsed from the engine's own constants -------------------

def emp_consts(rel: str, names: list[str]) -> dict[str, int]:
    """`pub const NAME = <int|$hex|A >> B|A * B>` out of an .emp source.

    Deliberately tiny: it resolves only the forms the constants this gate needs are
    actually written in, and raises on anything else rather than guessing. A gate that
    silently defaults a geometry constant is a gate measuring the wrong rectangle.
    """
    txt = open(os.path.join(AEON, rel)).read()
    out: dict[str, int] = {}

    def val(tok: str) -> int:
        tok = tok.strip()
        if tok.startswith("$"):
            return int(tok[1:], 16)
        if tok.isdigit():
            return int(tok)
        if tok in out:
            return out[tok]
        raise SetupError(f"cannot resolve {tok!r} while reading constants from {rel}")

    for n in names:
        m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(n)}\s*=\s*([^/\n]+)", txt, re.M)
        if not m:
            raise SetupError(f"cannot find `const {n}` in {rel}")
        expr = m.group(1).strip()
        if ">>" in expr:
            a, b = expr.split(">>", 1)
            out[n] = val(a) >> val(b)
        elif "*" in expr:
            acc = 1
            for part in expr.split("*"):
                acc *= val(part)
            out[n] = acc
        else:
            out[n] = val(expr)
    return out


# ---- readback ---------------------------------------------------------------

async def _c(b, method, params, timeout=180.0):
    return await asyncio.wait_for(b.call(method, params), timeout=timeout)


def _hex(r) -> str:
    return str(r["bytes"]).removeprefix("0x").removeprefix("0X").upper()


async def read_block(b, method: str, addr: int, n: int) -> bytes:
    raw, off = "", 0
    while off < n:
        k = min(MAX_READ, n - off)
        h = _hex(await _c(b, method, {"addr": hex(addr + off), "len": k}))
        if len(h) != 2 * k:
            raise SetupError(f"{method} returned {len(h)//2} bytes at {addr+off:#x}, wanted {k}")
        raw += h
        off += k
    return bytes.fromhex(raw)


async def read_word(b, addr: int) -> int:
    return int(_hex(await _c(b, "emulator/read_memory", {"addr": hex(addr), "len": 2})), 16)


async def read_long(b, addr: int) -> int:
    return int(_hex(await _c(b, "emulator/read_memory", {"addr": hex(addr), "len": 4})), 16)


STATE = ["Cache_Left_Col", "Cache_Head_Col", "Cache_Origin_Col", "Cache_Origin_Row",
         "Cache_Top_Row", "Cache_Bottom_Row",
         "Section_Left_Col_Written", "Section_Right_Col_Written",
         "Section_Top_Row_Written", "Section_Bottom_Row_Written",
         "Cache_Fill_Resume_Col", "Cache_Fill_Resume_Row",
         "Cache_Fill_RowResume_Row", "Cache_Fill_RowResume_Col"]

NO_PARTIAL = 0xFFFF     # the sentinel TileCache_Fill{Column,Row} store on completion


def cheat_debug_fly_bit() -> int:
    """The debug-fly cheat bit, DERIVED from the game's own constant, never hardcoded.

    `games/sonic4/config/constants.emp` declares it as `1 << 0`. Parsing it means a lane that
    renumbers the cheat bits breaks this gate loudly instead of arming the wrong cheat and
    reporting a clean vertical run that never entered free-flight — which would be a green
    result off a drive that never happened.
    """
    src = os.path.join(AEON, "games/sonic4/config/constants.emp")
    with open(src) as fh:
        for line in fh:
            m = re.match(r"\s*pub const CHEAT_DEBUG_FLY\s*=\s*1\s*<<\s*(\d+)", line)
            if m:
                return 1 << int(m.group(1))
    raise SetupError(f"CHEAT_DEBUG_FLY is not declared as `1 << N` in {src} — refusing to "
                     f"guess which bit arms debug-fly")


def word_at(buf: bytes, i: int) -> int:
    return (buf[i] << 8) | buf[i + 1]


class Sample:
    """One settled frame: the streaming state, the cache, and plane A."""

    def __init__(self, st, cam_x, cam_y, cache, plane, k):
        self.st, self.cam_x, self.cam_y, self.k = st, cam_x, cam_y, k
        self.cache, self.plane = cache, plane

    # -- the engine's own addressing, spelled once --
    def cache_word(self, world_col: int, world_row: int) -> int:
        phys_c = (world_col - self.st["Cache_Left_Col"] + self.st["Cache_Origin_Col"]) \
            % self.k["TILE_CACHE_COLS"]
        phys_r = (self.st["Cache_Origin_Row"] + (world_row - self.st["Cache_Top_Row"])) \
            % self.k["TILE_CACHE_ROWS"]
        return word_at(self.cache, (phys_r * self.k["TILE_CACHE_STRIDE"] + phys_c) * 2)

    def plane_word(self, world_col: int, world_row: int) -> int:
        p = (world_row % self.k["PLANE_V_CELLS"]) * self.k["PLANE_H_CELLS"] \
            + (world_col % self.k["PLANE_H_CELLS"])
        return word_at(self.plane, p * 2)

    def tested_cols(self):
        cam_col = self.cam_x >> 3
        lo = max(cam_col, self.st["Section_Left_Col_Written"], self.st["Cache_Left_Col"])
        hi = min(cam_col + self.k["SCREEN_LAST_COL_MAX"],
                 self.st["Section_Right_Col_Written"], self.st["Cache_Head_Col"])
        return lo, hi

    def tested_rows(self):
        cam_row = self.cam_y >> 3
        lo = max(cam_row, self.st["Section_Top_Row_Written"], self.st["Cache_Top_Row"])
        hi = min(cam_row + self.k["SCREEN_LAST_ROW_MAX"],
                 self.st["Section_Bottom_Row_Written"], self.st["Cache_Bottom_Row"])
        return lo, hi


async def take_sample(b, sym, k) -> Sample:
    st = {n: await read_word(b, sym[n]) for n in STATE}
    cam_x = (await read_long(b, sym["Camera_X"])) >> 16
    cam_y = (await read_long(b, sym["Camera_Y"])) >> 16
    nt_bytes = k["TILE_CACHE_COLS"] * k["TILE_CACHE_ROWS"] * 2
    cache = await read_block(b, "emulator/read_memory", sym["Tile_Cache_Nametable"], nt_bytes)
    plane = await read_block(b, "emulator/read_vram", k["VRAM_PLANE_A"],
                             k["PLANE_H_CELLS"] * k["PLANE_V_CELLS"] * 2)
    return Sample(st, cam_x, cam_y, cache, plane, k)


# ---- the two assertions ------------------------------------------------------

def check_partial_outside_claim(s: Sample) -> list[str]:
    """Assertion 2 — the pending partial fill must not be inside the recorded window."""
    out = []
    rc, rr = s.st["Cache_Fill_Resume_Col"], s.st["Cache_Fill_RowResume_Row"]
    if rc != NO_PARTIAL and s.st["Section_Left_Col_Written"] <= rc <= s.st["Section_Right_Col_Written"]:
        out.append(
            f"column {rc} is only PARTIALLY filled (Cache_Fill_Resume_Col={rc}, resume row "
            f"{s.st['Cache_Fill_Resume_Row']}, cache rows run {s.st['Cache_Top_Row']}.."
            f"{s.st['Cache_Bottom_Row']}) yet the streamer records it written "
            f"(Section_Left_Col_Written={s.st['Section_Left_Col_Written']}, "
            f"Section_Right_Col_Written={s.st['Section_Right_Col_Written']}). Its unfilled rows "
            f"were drawn into plane A from a ring slot the fill never wrote, and the record "
            f"means nothing will redraw them")
    if rr != NO_PARTIAL and s.st["Section_Top_Row_Written"] <= rr <= s.st["Section_Bottom_Row_Written"]:
        out.append(
            f"row {rr} is only PARTIALLY filled (Cache_Fill_RowResume_Row={rr}, resume col "
            f"{s.st['Cache_Fill_RowResume_Col']}, cache cols run {s.st['Cache_Left_Col']}.."
            f"{s.st['Cache_Head_Col']}) yet the streamer records it written "
            f"(Section_Top_Row_Written={s.st['Section_Top_Row_Written']}, "
            f"Section_Bottom_Row_Written={s.st['Section_Bottom_Row_Written']})")
    return out


def check_plane_matches_cache(s: Sample) -> tuple[list[str], int]:
    """Assertion 1 — every recorded, on-screen, cached cell agrees with plane A.

    Returns (messages, cells_tested). An EMPTY tested set is unmeasurable, not a pass;
    the caller turns cells_tested == 0 into a failure.
    """
    c_lo, c_hi = s.tested_cols()
    r_lo, r_hi = s.tested_rows()
    if c_hi < c_lo or r_hi < r_lo:
        return [], 0
    bad, tested = [], 0
    for col in range(c_lo, c_hi + 1):
        n_mismatch = n_cache = n_plane = 0
        for row in range(r_lo, r_hi + 1):
            cw, pw = s.cache_word(col, row), s.plane_word(col, row)
            tested += 1
            if cw:
                n_cache += 1
            if pw:
                n_plane += 1
            if cw != pw:
                n_mismatch += 1
        if n_mismatch:
            kind = ("INTERIOR HOLE (cache has tiles, plane A is empty)" if n_cache and not n_plane
                    else "wrong content")
            bad.append((col, n_mismatch, n_cache, n_plane, kind))
    msgs = []
    for col, n, nc, npl, kind in bad:
        msgs.append(
            f"world column {col}: {n} of {r_hi - r_lo + 1} recorded on-screen rows disagree — "
            f"{kind}; cache holds {nc} non-empty cells there, plane A holds {npl}. "
            f"Recorded window cols {c_lo}..{c_hi} rows {r_lo}..{r_hi}, camera "
            f"({s.cam_x},{s.cam_y}), cache cols {s.st['Cache_Left_Col']}.."
            f"{s.st['Cache_Head_Col']} origin {s.st['Cache_Origin_Col']}, rows "
            f"{s.st['Cache_Top_Row']}..{s.st['Cache_Bottom_Row']} origin "
            f"{s.st['Cache_Origin_Row']}")
    return msgs, tested


def control_lines(s: Sample) -> list[str]:
    """The neighbour control. Ring indexing is the trap this gate was born from, so the
    gate can be asked to show its own arithmetic: five adjacent world columns, their
    physical slots, and their occupancy. Adjacent world columns MUST land on adjacent
    physical slots (mod COLS) — if they do not, every occupancy number above is fiction."""
    c_lo, c_hi = s.tested_cols()
    mid = (c_lo + c_hi) // 2
    r_lo, r_hi = s.tested_rows()
    out = [f"      ring control at world cols {mid-2}..{mid+2} "
           f"(Left={s.st['Cache_Left_Col']} Origin={s.st['Cache_Origin_Col']} "
           f"COLS={s.k['TILE_CACHE_COLS']})"]
    prev = None
    for col in range(mid - 2, mid + 3):
        phys = (col - s.st["Cache_Left_Col"] + s.st["Cache_Origin_Col"]) % s.k["TILE_CACHE_COLS"]
        occ = sum(1 for r in range(r_lo, r_hi + 1) if s.cache_word(col, r))
        step = "" if prev is None else f"  (+{(phys - prev) % s.k['TILE_CACHE_COLS']})"
        out.append(f"        world {col} -> phys {phys}{step}, {occ} non-empty cache cells")
        prev = phys
    return out


# ---- driver ------------------------------------------------------------------

async def body(sock, rom, lst, blob, args, k):
    sym = parse_lst(lst)
    for n in STATE + ["Camera_X", "Camera_Y", "Tile_Cache_Nametable"]:
        if n not in sym:
            raise SetupError(f"symbol {n!r} did not resolve in {lst} — the gate "
                             f"cannot locate its subject")

    b = BusClient(sock, client_id="tilecachefill", client_name="tile_cache_fill_gate")
    await b.connect()
    st = await _c(b, "emulator/status", {})
    if st["romBytes"] != len(blob):
        raise SetupError(f"server serves {st['romBytes']} bytes, {rom} is {len(blob)} — "
                         f"refusing to gate a different ROM")
    print(f"      server romPath={st['romPath']} romBytes={st['romBytes']} (matches)")

    await _c(b, "emulator/run_frames", {"frames": args.settle})

    failures: list[str] = []
    total_cells = 0
    partial_seen = 0
    unmeasured = 0
    measured = 0
    first_x = last_x = None
    first_y = last_y = None
    printed_control = False

    # --- arm the vertical drive, if that is what was asked for -----------------
    #
    # WHY THIS MODE EXISTS. Every run of this gate before 2026-08-30 held RIGHT, so the
    # camera's Y never moved and THE VERTICAL FILL PATH WAS NEVER EXERCISED UNDER LOAD.
    # It carries the identical DECLARED-before-FILLED exposure as the column path
    # (`Tile_Cache_Fill` commits `Cache_Top_Row`/`Cache_Bottom_Row` before filling, exactly
    # as it commits `Cache_Head_Col`), and the row half of both assertions has therefore
    # never been given anything to find. The booked next step for the canopy gap is
    # precisely this run; see DEFERRED_WORK's canopy entry.
    #
    # Debug-fly is a CHEAT, not build-time equipment: the payload ships in every shape and
    # is unreachable until `Cheat_Flags` bit 0 is set (CODING_CONVENTIONS 1.7), so arming it
    # from the bus is the supported route and needs no special build.
    if args.drive == "fly":
        if "Cheat_Flags" not in sym:
            raise SetupError("Cheat_Flags did not resolve — cannot arm debug-fly")
        cur = await _c(b, "emulator/read_memory", {"addr": hex(sym["Cheat_Flags"]), "len": 1})
        await _c(b, "emulator/write_memory",
                 {"addr": hex(sym["Cheat_Flags"]),
                  "value": int(cur["bytes"], 16) | cheat_debug_fly_bit(), "width": 1})
        # B is edge-triggered off Ctrl_1_Press, so it needs a real press-and-release.
        await _c(b, "emulator/play_input",
                 {"rows": [{"start": 0, "end": 2, "buttons": ["b"]}], "maxFrames": 2})
        await _c(b, "emulator/release_all", {})
        await _c(b, "emulator/run_frames", {"frames": 2})

    for i in range(args.samples):
        # In fly mode sweep the camera DOWN then UP in alternating blocks, so the run
        # exercises both row directions rather than only the one the act happens to start
        # against. `right` is held alongside so columns keep streaming too — a vertical-only
        # run would leave the column half of the assertion measuring nothing, which this
        # gate reports as unmeasured rather than green, but which would still waste the run.
        if args.drive == "fly":
            vert = "down" if (i // max(1, args.flip)) % 2 == 0 else "up"
            buttons = [vert] if args.no_right else [vert, "right"]
        else:
            buttons = ["right"]
        await _c(b, "emulator/play_input",
                 {"rows": [{"start": 0, "end": args.step, "buttons": buttons}],
                  "maxFrames": args.step})
        await _c(b, "emulator/release_all", {})
        await _c(b, "emulator/run_frames", {"frames": args.post})

        s = await take_sample(b, sym, k)
        if first_x is None:
            first_x = s.cam_x
            first_y = s.cam_y
        last_x = s.cam_x
        last_y = s.cam_y
        if s.st["Cache_Fill_Resume_Col"] != NO_PARTIAL or \
                s.st["Cache_Fill_RowResume_Row"] != NO_PARTIAL:
            partial_seen += 1

        if args.control and not printed_control:
            for line in control_lines(s):
                print(line)
            printed_control = True

        for msg in check_partial_outside_claim(s):
            failures.append(f"FAIL sample {i} (camX={s.cam_x}): {msg}")
        msgs, tested = check_plane_matches_cache(s)
        total_cells += tested
        if tested == 0:
            # NOT a per-sample failure. An empty intersection means the recorded window
            # has fallen entirely off the screen — the streamer could not keep up, which
            # is what a hard-starved fill is SUPPOSED to look like once the loops refuse
            # to record what they did not write. It proves nothing either way, so it is
            # counted and reported, and only a run in which NOTHING was measurable is a
            # verdict (below).
            unmeasured += 1
        else:
            measured += 1
        for msg in msgs:
            failures.append(f"FAIL sample {i}: {msg}")

        if len(failures) >= args.max_failures:
            print(f"      stopping early: {len(failures)} failures reached the report cap")
            break

    # The anti-vacuity guard is about the axis this run actually DRIVES. A fly run whose
    # camY never moved has not exercised the row path, and reporting it green would be the
    # exact "couldn't measure rendered as pass" failure this gate refuses elsewhere.
    if first_x is None:
        raise SetupError("no sample was taken at all")
    if args.drive == "fly":
        if last_y == first_y:
            raise SetupError(
                f"the camera's Y never moved (camY stayed {first_y}) across "
                f"{args.samples} samples of held UP/DOWN with debug-fly armed. The vertical "
                f"fill path was NOT exercised, so this run proves nothing about the row axis "
                f"- which is the only reason to run --drive fly. Check that Cheat_Flags bit 0 "
                f"took and that B entered free-flight")
    elif last_x == first_x:
        raise SetupError(
            f"the camera did not move (camX stayed {first_x}). Holding RIGHT produced no "
            f"travel, so no column was ever streamed and this run proves nothing")

    if measured == 0:
        raise SetupError(
            f"not one of the {args.samples} samples had a recorded window that intersected the "
            f"screen inside the cache, so NOTHING was ever compared. The streamer never kept up "
            f"with the camera on this ROM — refusing to report a verdict off a run that measured "
            f"nothing")

    print(f"      camera travelled X {first_x} -> {last_x}, Y {first_y} -> {last_y} px over "
          f"{args.samples} samples x {args.step}+{args.post} frames (drive={args.drive})")
    print(f"      {total_cells} recorded on-screen cells compared against the tile cache "
          f"at {measured} sample points")
    if unmeasured:
        print(f"      CAVEAT: {unmeasured} sample point(s) compared NOTHING — the recorded "
              f"window had fallen entirely off screen (the streamer could not keep up). Those "
              f"samples prove nothing either way")
    print(f"      a partial fill was outstanding at {partial_seen} of the sample points "
          f"(0 means the starved regime was never entered — see POISON in the docstring)")
    return failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=os.path.join(AEON, "s4.debug.bin"))
    ap.add_argument("--lst", default=None,
                    help="listing for the symbols (default: the ROM's own .lst)")
    ap.add_argument("--settle", type=int, default=180,
                    help="frames from reset to gameplay before the first sample")
    ap.add_argument("--samples", type=int, default=40)
    ap.add_argument("--step", type=int, default=8, help="frames of held RIGHT per sample")
    ap.add_argument("--post", type=int, default=3,
                    help="frames with the buttons released before sampling, so the plane "
                         "buffer drains; 0 reintroduces the drain-lag false positive")
    ap.add_argument("--max-failures", type=int, default=12)
    ap.add_argument("--drive", choices=("right", "fly"), default="right",
                    help="right: hold RIGHT (the original horizontal run). fly: arm the "
                         "debug-fly cheat and sweep the camera vertically, which is the "
                         "axis this gate had never been pointed at")
    ap.add_argument("--flip", type=int, default=6,
                    help="fly mode: samples per vertical direction before reversing")
    ap.add_argument("--no-right", action="store_true",
                    help="fly mode: sweep vertically ONLY, without holding RIGHT")
    ap.add_argument("--control", action="store_true",
                    help="print the neighbour control that proves the ring indexing")
    args = ap.parse_args()

    rom = os.path.abspath(args.rom)
    lst = os.path.abspath(args.lst) if args.lst else rom[:-4] + ".lst"
    try:
        blob = open(rom, "rb").read()
    except OSError as e:
        print(f"tile_cache_fill_gate: SETUP — {e}", file=sys.stderr)
        return 2
    if not os.path.exists(lst):
        print(f"tile_cache_fill_gate: SETUP — no listing at {lst}", file=sys.stderr)
        return 2

    print(f"ROM   {rom}")
    print(f"      {len(blob)} bytes, crc32 {zlib.crc32(blob) & 0xFFFFFFFF:08x}")

    try:
        k = emp_consts("engine/system/constants.emp",
                       ["SCREEN_WIDTH", "SCREEN_HEIGHT", "TILE_CACHE_COLS", "TILE_CACHE_ROWS",
                        "TILE_CACHE_STRIDE", "PLANE_H_CELLS", "PLANE_V_CELLS",
                        "VRAM_PLANE_A", "BLOCK_DECOMP_BUDGET"])
    except SetupError as e:
        print(f"tile_cache_fill_gate: SETUP — {e}", file=sys.stderr)
        return 2
    # SCREEN_LAST_{COL,ROW}_MAX are written as (7 + SCREEN_X - 1) >> 3 — a form the tiny
    # parser above does not evaluate. Derive them here from the two dimensions instead,
    # spelled the same way the .emp spells them, so they still cannot be a pinned number.
    k["SCREEN_LAST_COL_MAX"] = (7 + k["SCREEN_WIDTH"] - 1) >> 3
    k["SCREEN_LAST_ROW_MAX"] = (7 + k["SCREEN_HEIGHT"] - 1) >> 3
    print(f"      geometry from engine/system/constants.emp: cache "
          f"{k['TILE_CACHE_COLS']}x{k['TILE_CACHE_ROWS']}, plane "
          f"{k['PLANE_H_CELLS']}x{k['PLANE_V_CELLS']} at {k['VRAM_PLANE_A']:#06x}, screen "
          f"{k['SCREEN_LAST_COL_MAX']+1}x{k['SCREEN_LAST_ROW_MAX']+1} cells, "
          f"BLOCK_DECOMP_BUDGET={k['BLOCK_DECOMP_BUDGET']}")

    inst = AetherInstance(rom, symbols=lst)
    try:
        sock = inst.start()
    except Exception as e:                      # noqa: BLE001 — spawn failure is setup
        print(f"tile_cache_fill_gate: SETUP — {e}", file=sys.stderr)
        return 2
    try:
        failures = asyncio.run(body(sock, rom, lst, blob, args, k))
    except SetupError as e:
        print(f"tile_cache_fill_gate: SETUP — {e}", file=sys.stderr)
        return 2
    except asyncio.TimeoutError:
        print("tile_cache_fill_gate: SETUP — an RPC exceeded its deadline (emulator wedge)",
              file=sys.stderr)
        return 2
    finally:
        inst.reap()

    print()
    if failures:
        for f in failures:
            print(f"  {f}")
        print(f"RED   {len(failures)} violation(s): the streamer recorded cells it did not "
              f"write, so they will never be redrawn")
        return 1
    print("GREEN every cell the section streamer recorded as written matches the tile cache, "
          "and no partial fill was ever inside the recorded window")
    return 0


if __name__ == "__main__":
    sys.exit(main())
