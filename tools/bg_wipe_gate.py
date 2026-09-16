#!/usr/bin/env python3
"""GATE BG-WIPE — does crossing into a region with a DIFFERENT background repaint the plane?

WHAT THIS EXISTS TO STOP, stated as the failure and not as the feature.

Until regions part 2 step 6, Plane B was painted once at level init (and again at cache
recovery / the DEBUG warp) and CONTINUOUS SCROLLING NEVER REPAINTED IT. Cross into a region
whose `rg_bg_layout` names a different blob and the plane kept showing the old backdrop,
for ever, with nothing in the build or in any ROM-side test to say so. Step 6 is the
repaint: an amortised row sweep, `BG_WIPE_ROWS_PER_FRAME` rows a frame, carried by
`BG_Stream_Update` and produced through the ordinary `Draw_BG_TileRow`.

This gate has to be able to see THREE distinct failures, and each leg below names which:

  * A WIPE THAT DOES NOT HAPPEN — the cursor never arms, or arms and never retires, or the
    plane still holds the old blob when it does.  Legs ARM, RATE, DONE, FINAL.
  * A WIPE THAT HAPPENS WRONGLY — the cursor advances past rows that were never drawn, so
    the tracker's account of what it has covered disagrees with the VDP.  Leg COVERED reads
    BOTH and compares them; it is the only leg that can catch a cursor running ahead of the
    producer, which is the exact reason `Draw_BG_TileRow` returns an admitted flag at all.
  * A WIPE THAT HAPPENS IN THE WRONG ORDER — the design call of step 6 is that the sweep
    starts at the TOP VISIBLE plane row and walks down, so the rows the player is looking at
    are repainted first and the E2 transient (new palette over old art, from frame 0) is
    cleared in ceil(BG_SCREEN_ROWS / BG_WIPE_ROWS_PER_FRAME) frames instead of lasting the
    whole sweep.  Leg VISIBLE grades that, and it is red against any order that does not put
    the visible span first — including §4.3's own "hidden rows first" and a plain top-down
    walk from plane row 0.

AND ONE FAILURE IN THE OTHER DIRECTION, which is why leg CONTROL exists: a wipe that fires
on EVERY crossing would repaint the plane with the picture it already holds, 64 rows at a
time, on every region boundary in the act. CONTROL crosses a boundary whose two rows have
the SAME effective layout and asserts the cursor stays 0. It is green before step 6 and
green after — deliberately, so that a gate which has quietly become unable to fail shows up.

TWO ROUTES, because a region crossing has two shapes and only one of them was designed for.

  HORIZONTAL — fly RIGHT across the tall region's left edge. The camera Y does not move, so
  `BG_Plane_Top` is stationary for the whole sweep and the COVERED comparison is exact.

  VERTICAL — fly DOWN across the tall region's top edge. `REGIONS-VERTICAL-CROSSING-ON-LANDING`
  measured that a fall changes region with NO horizontal travel at all, which is what left
  §4.3's "sweep from the entry side" with no answer. DEBUG free flight descends at
  PLAYER_DEBUG_FLY_SPEED, which the source says is "matched to CAM_MAX_Y_STEP" — this gate
  MEASURES that per-tick camera delta rather than believing the comment, because if the two
  ever diverge the vertical leg stops being the worst case it is here to be. The window
  MOVES during this sweep, so COVERED is not asserted here (a row drawn three ticks ago was
  drawn against a different `BG_Plane_Top`); ARM, RATE, DONE and a settled FINAL are.

WHAT A GREEN HERE DOES NOT SAY.

  * It says nothing about what the wipe LOOKS like. The step-5 tall blob's rows 0..63 are
    the shipped act background with one cell changed (the row marker, `tools/gen_tall_bg_test.py`),
    so the byte difference this gate reads to the byte is, on screen, one column of tiles.
    The visible showcase is a second real layout, which the hub's FIRST-SHOWCASE ruling put
    on a follow-up card, not in step 6.
  * It says nothing about a real gravity FALL's landing transient — the vertical leg holds
    DOWN in free flight, which is the camera's worst case but not the player's.
  * It says nothing about the parallax BANDS, which alias against plane space in this very
    region (BG-BAND-PLANE-ANCHOR, deliberately open). This gate reads the nametable.

Every expectation is DERIVED — from constants parsed out of the engine's own sources, from
the region table read out of the ROM, and from the two tracker bytes read out of the machine
at the sampling instant. Nothing is copied from a table in `docs/DEFERRED_WORK.md`: that
table was measured stale at exactly this spot twice.

Exit: 0 PASS · 1 FAIL · 2 COULD NOT RUN (a premise the gate refuses to measure past).
"""
import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

AEON = Path(os.environ.get("AEON_DIR",
                           Path(__file__).resolve().parent.parent)).resolve()
sys.path.insert(0, str(AEON / "tools"))
from suite_paths import add_client_path                            # noqa: E402
add_client_path()
from aether import BusClient                                       # noqa: E402
from aether_instance import (AetherInstance, SpawnError,           # noqa: E402
                             WrongServerError, read_bytes, unprefix)
from raster_cost_probe import parse_lst                            # noqa: E402
import region_table                                                # noqa: E402

VRAM_PLANE_B = 0xE000          # engine/system/constants.emp VRAM_PLANE_B_BYTES
BOOT_MAX_FRAMES = 1200
TICK_MAX_FRAMES = 30
WALK_MAX_TICKS = 400
SETTLE_TICKS = 8


class GateError(RuntimeError):
    """A premise this gate refuses to measure past — exit 2, never a pass."""


class Failure(RuntimeError):
    """A real red — exit 1."""


# ---------------------------------------------------------------------------
# Constants, each re-derived from the source that declares it.
# ---------------------------------------------------------------------------
def _const(rel, name):
    text = (AEON / rel).read_text(errors="replace")
    m = re.search(rf"^\s*(?:pub\s+)?const\s+{re.escape(name)}\s*=\s*(\d+)\s*(?://|$)",
                  text, re.M)
    if not m:
        raise GateError(
            f"{rel} no longer declares `const {name} = <int>`. Every expectation in "
            f"tools/bg_wipe_gate.py is derived from it, so this is a SETUP FAILURE and must "
            f"not be defaulted to a remembered value.")
    return int(m.group(1))


class Consts:
    def __init__(self, lst):
        C = "engine/system/constants.emp"
        B = "engine/level/bg.emp"
        self.PLANE_H_CELLS = _const(C, "PLANE_H_CELLS")
        self.PLANE_V_CELLS = _const(C, "PLANE_V_CELLS")
        self.SCREEN_HEIGHT = _const(C, "SCREEN_HEIGHT")
        self.HALF_W = _const(C, "CAM_SCREEN_HALF_W")
        self.HALF_H = _const(C, "CAM_SCREEN_HALF_H")
        self.CAM_MAX_Y_STEP = _const(C, "CAM_MAX_Y_STEP")
        self.FLY = _const("games/sonic4/player/player_common.emp", "PLAYER_DEBUG_FLY_SPEED")
        self.WIPE_ROWS = _const(B, "BG_WIPE_ROWS_PER_FRAME")
        self.PLANE_B_CELL_ROWS = _const("engine/level/parallax.emp", "PLANE_B_CELL_ROWS")
        self.MAX_STEP_ROWS = _const("engine/level/parallax.emp", "BG_VSCROLL_MAX_STEP_ROWS")
        self.PLANE_B_SPAN = self.PLANE_B_CELL_ROWS * 8
        self.ROW_PX = self.PLANE_B_SPAN // self.PLANE_B_CELL_ROWS
        # engine/level/bg.emp: BG_WIPE_TOTAL_ROWS = PLANE_V_CELLS
        self.WIPE_TOTAL = self.PLANE_V_CELLS
        # engine/level/bg.emp: BG_WIPE_FRAMES = ceil(TOTAL / ROWS_PER_FRAME)
        self.WIPE_FRAMES = -(-self.WIPE_TOTAL // self.WIPE_ROWS)
        # engine/level/bg.emp: BG_SCREEN_ROWS / BG_STREAM_SPARE_ROWS / BG_STREAM_LEAD_ROWS
        self.SCREEN_ROWS = self.SCREEN_HEIGHT // self.ROW_PX + 1
        self.SPARE_ROWS = self.PLANE_V_CELLS - self.SCREEN_ROWS
        self.LEAD = self.SPARE_ROWS // 2
        # THE VISIBLE-SPAN DEADLINE. With the window STATIONARY a sweep that starts at the top
        # visible row covers all BG_SCREEN_ROWS of it after ceil(SCREEN_ROWS / WIPE_ROWS)
        # spends, and the arming call is the first spend — so the sample is taken VIS_TICKS
        # ticks after the arming tick.
        #
        # THE WORST-CASE FORM WAS TRIED FIRST AND REJECTED AS VACUOUS, which is worth the
        # sentence. If the scroll runs downward at the rate clamp's full MAX_STEP_ROWS every
        # tick, the visible span races under the sweep and the true bound is
        # ceil(SCREEN_ROWS / (WIPE_ROWS - MAX_STEP_ROWS)) = 15 ticks of a 16-tick sweep —
        # a deadline the sweep meets by FINISHING, which tests nothing. So the deadline stays
        # nominal and the drift the run ACTUALLY produced is measured at the sample and
        # converted into an allowance there (`drift_allowance` below). Derived, not tuned,
        # and it goes red on an order that puts the visible rows anywhere but first.
        self.VIS_TICKS = -(-self.SCREEN_ROWS // self.WIPE_ROWS)
        self.ROW_BYTES = self.PLANE_H_CELLS * 2
        self.PLANE_BYTES = self.ROW_BYTES * self.PLANE_V_CELLS

        # TWO NAMESPACES, ONE INTERFACE — and only one of them carries these names. The
        # listing's EQU block holds engine.constants' globally-injected consts; a `pub const`
        # local to engine/level/bg.emp (BG_WIPE_ROWS_PER_FRAME, BG_WIPE_TOTAL_ROWS) never
        # appears there, so it CANNOT be cross-checked against the artifact this way and
        # pretending otherwise would be the vacuous half of a real check. What covers those
        # two instead is BEHAVIOURAL and sharper: leg ARM asserts the cursor lands on exactly
        # WIPE_TOTAL - WIPE_ROWS on the crossing tick and leg RATE asserts the whole
        # decrement sequence, so a source figure the ROM does not implement goes red with the
        # measured sequence printed beside the wanted one. Recorded here, and printed on
        # every run, so a reader does not take the cross-check below for more than it is.
        txt = Path(lst).read_text(errors="replace")
        self.source_only = []
        for nm, val in (("PLANE_V_CELLS", self.PLANE_V_CELLS),
                        ("SCREEN_HEIGHT", self.SCREEN_HEIGHT),
                        ("CAM_MAX_Y_STEP", self.CAM_MAX_Y_STEP),
                        ("BG_WIPE_ROWS_PER_FRAME", self.WIPE_ROWS),
                        ("BG_WIPE_TOTAL_ROWS", self.WIPE_TOTAL)):
            m = re.search(rf"^EQU\s+{nm}\s*=\s*\$([0-9A-Fa-f]+)\s*$", txt, re.M)
            if m is None:
                self.source_only.append(nm)
                continue
            if int(m.group(1), 16) != val:
                raise GateError(
                    f"{nm} is {val} in source but ${m.group(1)} = {int(m.group(1), 16)} in the "
                    f"listing. The source tree and the built ROM disagree — this gate would "
                    f"grade one against the other's arithmetic.")
        if "PLANE_V_CELLS" in self.source_only:
            raise GateError(
                "`EQU PLANE_V_CELLS = $..` is not in the listing. Every row address in this "
                "gate is that number, and with no line to cross-check it cannot prove the "
                "source it read built the ROM it is about to drive.")
        if self.ROW_PX != 8:
            raise GateError(
                f"BG_VSCROLL_ROW_PX derives to {self.ROW_PX}, not 8, but the engine spells the "
                f"pixel->row conversion as a literal `lsr.w #3`.")
        if self.FLY != self.CAM_MAX_Y_STEP:
            raise GateError(
                f"PLAYER_DEBUG_FLY_SPEED is {self.FLY} and CAM_MAX_Y_STEP is "
                f"{self.CAM_MAX_Y_STEP}. The vertical leg's whole claim to be the WORST CASE "
                f"vertical entry is that free flight descends at the camera's own clamp "
                f"ceiling. They have diverged, so it is no longer that, and the leg would "
                f"report a green about a slower descent than the game can produce.")


    def drift_allowance(self, ticks_after_arm, drift_rows):
        """How many VISIBLE plane rows the sweep is allowed to have missed at this sample.

        After `ticks_after_arm` further spends the sweep has drawn WIPE_ROWS * (ticks + 1)
        rows from the row that was the top visible one at the arm. The visible span has since
        slid `drift_rows` rows down. Its bottom is therefore drift + SCREEN_ROWS - 1 rows
        below that start, and the sweep's frontier is WIPE_ROWS * (ticks + 1) - 1 below it,
        so exactly the excess is allowed to be missing."""
        frontier = self.WIPE_ROWS * (ticks_after_arm + 1) - 1
        bottom = drift_rows + self.SCREEN_ROWS - 1
        return max(0, bottom - frontier)

    def describe(self):
        return (f"plane {self.PLANE_H_CELLS}x{self.PLANE_V_CELLS}, row {self.ROW_BYTES} B; "
                f"wipe {self.WIPE_ROWS} rows/frame x {self.WIPE_FRAMES} frames = "
                f"{self.WIPE_TOTAL} rows; screen {self.SCREEN_ROWS} rows, lead {self.LEAD}; "
                f"visible span covered by tick {self.VIS_TICKS}; fly/camY cap "
                f"{self.FLY}/{self.CAM_MAX_Y_STEP} px")

    def want_top(self, vscroll, span):
        map_rows = (span // self.ROW_PX) if span else self.PLANE_V_CELLS
        max_top = max(0, map_rows - self.PLANE_V_CELLS)
        return max(0, min(max_top, (vscroll // self.ROW_PX) - self.LEAD)), max_top, map_rows


# ---------------------------------------------------------------------------
async def _c(b, method, params=None, timeout=180.0):
    return await asyncio.wait_for(b.call(method, params or {}), timeout=timeout)


async def rd(b, addr, width):
    return int(await read_bytes(b, addr, width), 16)


def s16(v):
    return v - 0x10000 if v >= 0x8000 else v


class Rig:
    """One logic tick at a time, sampled at the top of the game state's Update."""

    def __init__(self, b, sym, K, rom):
        self.b, self.sym, self.K, self.rom = b, sym, K, rom
        self.upd = sym["GameState_OJZScroll_Update"]

    async def boot(self, at):
        b, sym = self.b, self.sym
        await _c(b, "emulator/reset", {})
        r = await _c(b, "emulator/run_to", {"addr": hex(sym["GameState_OJZScroll_Init"]),
                                            "maxFrames": BOOT_MAX_FRAMES})
        if not r.get("reached"):
            raise GateError(f"run_to GameState_OJZScroll_Init never reached it: {r}")
        for nm, v, w in (("Boot_At_X", at[0], 2), ("Boot_At_Y", at[1], 2),
                         ("Boot_At_Flag", 1, 1)):
            await _c(b, "emulator/write_memory", {"addr": hex(sym[nm]), "value": v, "width": w})
        r = await _c(b, "emulator/run_to", {"addr": hex(self.upd), "maxFrames": BOOT_MAX_FRAMES})
        if not r.get("reached"):
            raise GateError(f"run_to GameState_OJZScroll_Update never reached it: {r}")

    async def tick(self):
        await _c(self.b, "emulator/step", {})
        r = await _c(self.b, "emulator/run_to", {"addr": hex(self.upd),
                                                 "maxFrames": TICK_MAX_FRAMES})
        if not r.get("reached"):
            raise GateError(f"the game state's Update did not come round within "
                            f"{TICK_MAX_FRAMES} frames: {r}")

    async def hold(self, button):
        await _c(self.b, "emulator/release_all", {})
        if button:
            await _c(self.b, "emulator/hold", {"buttons": [button], "down": True})

    async def plane(self):
        K, out = self.K, bytearray()
        for off in range(0, K.PLANE_BYTES, 4096):
            n = min(4096, K.PLANE_BYTES - off)
            r = await _c(self.b, "emulator/read_vram",
                         {"addr": hex(VRAM_PLANE_B + off), "len": n})
            h = unprefix(r["bytes"])
            if len(h) != n * 2:
                raise GateError(f"short VRAM read at +{off}: {len(h)} hex chars, wanted {n * 2}")
            out += bytes.fromhex(h)
        return bytes(out)

    async def sample(self, tag, want_plane=False):
        b, sym, K = self.b, self.sym, self.K
        cx = (await rd(b, sym["Camera_X"], 4)) >> 16
        cy = (await rd(b, sym["Camera_Y"], 4)) >> 16
        s = {"tag": tag,
             "centre": (cx + K.HALF_W, cy + K.HALF_H),
             "region": await rd(b, sym["Region_Current"], 4),
             "layout": await rd(b, sym["BG_Plane_Layout"], 4),
             "top": await rd(b, sym["BG_Plane_Top"], 2),
             "cursor": await rd(b, sym["BG_Wipe_Cursor"], 1),
             "row": await rd(b, sym["BG_Wipe_Row"], 1),
             "vscroll": s16(await rd(b, sym["Parallax_Current_Vscroll_BG"], 2))}
        if want_plane:
            s["plane"] = await self.plane()
        return s


def fmt(s):
    return ("  %-16s centre=%s vscroll=%4d top=%3d  cursor=%3d row=%2d  layout=$%06X  "
            "region=$%06X" % (s["tag"], s["centre"], s["vscroll"], s["top"], s["cursor"],
                              s["row"], s["layout"], s["region"]))


def covered_rows(s, K):
    """The PLANE rows the tracker CLAIMS the sweep has already drawn.

    `BG_Wipe_Row` is the next row it will draw and `BG_Wipe_Cursor` is how many are left, so
    exactly TOTAL - cursor rows have been drawn and they are the ones ending just before
    `BG_Wipe_Row`, walking down and wrapping. Derived from the two bytes rather than counted
    by this script, because the whole point of leg COVERED is to grade the tracker's own
    account against the VDP."""
    drawn = K.WIPE_TOTAL - s["cursor"]
    start = (s["row"] - drawn) % K.PLANE_V_CELLS
    return [(start + i) % K.PLANE_V_CELLS for i in range(drawn)]


def map_row_of(p, top, K):
    """The map row plane row `p` is showing with the window at `top`: the unique m in
    [top, top+PLANE_V_CELLS-1] with m = p (mod PLANE_V_CELLS). The engine derives it the
    same way, at engine/level/bg.emp's wipe loop."""
    return top + ((p - top) % K.PLANE_V_CELLS)


def blob_row(rom, base, m, K):
    at = base + m * K.ROW_BYTES
    if base == 0 or at + K.ROW_BYTES > len(rom):
        return None
    return rom[at:at + K.ROW_BYTES]


def classify(plane, p, top, K, rom, new_base, old_base):
    """EXACT: what is plane row p holding for the window at `top` — the NEW blob's row for
    that window, the OLD blob's, or neither? Used by leg FINAL, where the window has settled
    and the answer has to be the exact map row."""
    got = plane[p * K.ROW_BYTES:(p + 1) * K.ROW_BYTES]
    m = map_row_of(p, top, K)
    if got == blob_row(rom, new_base, m, K):
        return "new"
    if got == blob_row(rom, old_base, m, K):
        return "old"
    return "other"


def classify_blob(plane, p, K, rom, new_base, new_rows, old_base, old_rows):
    """WHICH BLOB did plane row p come from, whatever the window was when it was drawn?

    Leg COVERED cannot use the exact form above: the window MOVES during a sweep — measured,
    not hypothesised, on both routes in this ROM, because the tall region raises the scroll
    ceiling and the scroll then ratchets — so a row drawn six ticks ago was drawn against a
    different `BG_Plane_Top` and comparing it to the live one would go red on correct code.
    What leg COVERED actually asks is whether the cursor advanced past a row the producer
    never drew, and that question is answered by the BLOB alone: any map row m = p (mod 64)
    inside the map is a legal answer for `new`. Leg FINAL still pins the exact rows once the
    window has settled, so the pair covers both halves."""
    got = plane[p * K.ROW_BYTES:(p + 1) * K.ROW_BYTES]
    for base, rows, verdict in ((new_base, new_rows, "new"), (old_base, old_rows, "old")):
        m = p
        while m < rows:
            if got == blob_row(rom, base, m, K):
                return verdict
            m += K.PLANE_V_CELLS
    return "other"


# ---------------------------------------------------------------------------
async def walk(rig, button, done, tag, K):
    """Hold `button`, one sample a tick, until done(sample). Returns every sample."""
    await rig.hold(button)
    out = []
    for i in range(WALK_MAX_TICKS):
        await rig.tick()
        s = await rig.sample(f"{tag}{i}")
        out.append(s)
        if done(s):
            await rig.hold(None)
            return out
    await rig.hold(None)
    raise GateError(f"leg `{tag}` held {button} for {WALK_MAX_TICKS} ticks without arriving "
                    f"(last centre {out[-1]['centre']}, region ${out[-1]['region']:06X}) — "
                    f"the route has gone stale against the region table")


def check_rate(samples, i_arm, K, tag, fails):
    """The cursor must fall by exactly BG_WIPE_ROWS_PER_FRAME a tick and reach 0 on the
    derived tick. A refused row entry shows up here as a short step, which is the only
    externally visible consequence of the admitted-flag contract."""
    seq = [s["cursor"] for s in samples[i_arm:]]
    want = []
    c = K.WIPE_TOTAL - K.WIPE_ROWS      # the arming tick spends its budget in the same call
    while True:
        want.append(max(0, c))
        if c <= 0:
            break
        c -= K.WIPE_ROWS
    got = seq[:len(want)]
    if got != want:
        fails.append(f"{tag} RATE: the cursor ran {got} from the arming tick, wanted {want} "
                     f"(BG_WIPE_TOTAL_ROWS {K.WIPE_TOTAL} retiring {K.WIPE_ROWS} a tick). A "
                     f"SHORT step is a refused row entry the cursor correctly did not spend; "
                     f"a LONG one is the cursor running ahead of the producer.")
        return None
    # BG_WIPE_FRAMES counts SPENDS, and the arming call is the first of them — the crossing
    # tick both arms the cursor and buys its first BG_WIPE_ROWS_PER_FRAME rows in one
    # BG_Stream_Update call. So the number of FURTHER ticks is one less. Written out because
    # the first version of this gate compared the two directly and went red on correct code,
    # at 15 against 16.
    n = len(want) - 1
    if n != K.WIPE_FRAMES - 1:
        fails.append(f"{tag} DONE: the cursor reached 0 {n} ticks after the arming tick; "
                     f"BG_WIPE_FRAMES is {K.WIPE_FRAMES} spends and the arming tick is the "
                     f"first, so {K.WIPE_FRAMES - 1} further ticks is the derived answer")
    return i_arm + n


async def run_crossing(rig, K, rom, sym, button, start_at, row_from, row_to, eff_from, eff_to,
                       tag, fails):
    print(f"\n  ---- {tag}: row {row_from['index']} -> row {row_to['index']}, holding "
          f"{button.upper()} from {start_at} ----")
    await rig.boot(start_at)
    for _ in range(SETTLE_TICKS):
        await rig.tick()
    s0 = await rig.sample(f"{tag}.start")
    print(fmt(s0))
    if s0["region"] != row_from["addr"]:
        raise GateError(f"{tag}: booting at {start_at} resolved region $%06X, not row "
                        f"{row_from['index']} at $%06X. The route is written against the "
                        f"region table read out of THIS ROM, so this means the boot position "
                        f"does not land where the table says it does."
                        % (s0["region"], row_from["addr"]))
    if s0["layout"] != eff_from:
        raise GateError(f"{tag}: at the start BG_Plane_Layout is $%06X but row "
                        f"{row_from['index']}'s effective layout is $%06X — the plane is not "
                        f"holding what the region it is in names, before the crossing has "
                        f"even happened." % (s0["layout"], eff_from))
    if s0["cursor"] != 0:
        raise GateError(f"{tag}: a sweep is already in flight at the start "
                        f"(BG_Wipe_Cursor={s0['cursor']})")

    walked = await walk(rig, button, lambda s: s["region"] == row_to["addr"], tag, K)
    samples = [s0] + walked
    i_arm = next(i for i, s in enumerate(samples) if s["region"] == row_to["addr"])
    print(fmt(samples[i_arm - 1]))
    print(fmt(samples[i_arm]))

    # -- the flight really is the worst case, MEASURED not assumed --
    axis = 0 if button in ("left", "right") else 1
    steps = [abs(b["centre"][axis] - a["centre"][axis])
             for a, b in zip(samples[:i_arm + 1], samples[1:i_arm + 2])]
    if steps and max(steps) != K.FLY:
        raise GateError(f"{tag}: the held {button.upper()} moved the camera centre at most "
                        f"{max(steps)} px a tick on axis {axis}, not PLAYER_DEBUG_FLY_SPEED = "
                        f"{K.FLY}. This is not debug flight and the leg is not the worst-case "
                        f"entry it claims to be.")

    # ---- LEG ARM ----
    a = samples[i_arm]
    if a["layout"] != eff_to:
        fails.append(f"{tag} ARM: on the crossing tick BG_Plane_Layout is $%06X, but row "
                     f"{row_to['index']}'s effective layout is $%06X. The plane was never "
                     f"promised the new picture, so no sweep can deliver it."
                     % (a["layout"], eff_to))
    want_cursor = K.WIPE_TOTAL - K.WIPE_ROWS
    if a["cursor"] != want_cursor:
        fails.append(f"{tag} ARM: on the crossing tick BG_Wipe_Cursor is {a['cursor']}, wanted "
                     f"{want_cursor} (BG_WIPE_TOTAL_ROWS {K.WIPE_TOTAL} less the "
                     f"{K.WIPE_ROWS} the same call spends). 0 means the wipe never armed and "
                     f"the plane keeps the old backdrop for ever.")
        # DO NOT RETURN. A tree with no wipe at all has to reach leg FINAL and go RED there,
        # not stop early: a gate that exits before its strongest leg on the very failure it
        # exists for reports FEWER red legs the more broken the tree is.
        await settle_and_check_final(rig, K, rom, eff_to, eff_from, tag, fails)
        return None, None
    # THE START ROW is the design call: the sweep must begin at the top VISIBLE plane row.
    start_row = (a["row"] - K.WIPE_ROWS) % K.PLANE_V_CELLS
    vis_top = (a["vscroll"] // K.ROW_PX) % K.PLANE_V_CELLS
    if start_row != vis_top:
        fails.append(f"{tag} ARM: the sweep started at plane row {start_row}, but the scroll "
                     f"{a['vscroll']} puts the top VISIBLE plane row at {vis_top}. Step 6's "
                     f"order is 'top visible row, walking down' — a sweep that starts "
                     f"anywhere else holds the new-palette-over-old-art transient on screen "
                     f"for longer than ceil(BG_SCREEN_ROWS / BG_WIPE_ROWS_PER_FRAME) ticks.")

    # ---- LEG RATE / DONE ----
    n_needed = K.WIPE_FRAMES + 2
    while len(samples) - i_arm <= n_needed:
        await rig.tick()
        samples.append(await rig.sample(f"{tag}.w{len(samples)}"))
    i_done = check_rate(samples, i_arm, K, tag, fails)
    print(fmt(samples[i_arm + K.WIPE_FRAMES]))

    # ---- LEG VISIBLE / COVERED: read the plane back, mid-sweep ----
    # Re-run the crossing is not possible, so the mid-sweep read is taken on a SECOND pass
    # through the same route below; here we assert the settled picture.
    tops = [s["top"] for s in samples[i_arm:i_arm + K.WIPE_FRAMES + 1]]
    print(f"  {tag}: BG_Plane_Top over the sweep {tops[0]} -> {tops[-1]} "
          f"({len(set(tops))} distinct)")

    # ---- LEG FINAL ----
    await settle_and_check_final(rig, K, rom, eff_to, eff_from, tag, fails)
    return i_arm, i_done


async def settle_and_check_final(rig, K, rom, eff_to, eff_from, tag, fails):
    """LEG FINAL: once the sweep has had time to run, every plane row must hold the NEW blob's
    row for the live window."""
    for _ in range(SETTLE_TICKS * 4):
        await rig.tick()
    fin = await rig.sample(f"{tag}.final", want_plane=True)
    print(fmt(fin))
    bad = [p for p in range(K.PLANE_V_CELLS)
           if classify(fin["plane"], p, fin["top"], K, rom, eff_to, eff_from) != "new"]
    if bad:
        shown = ", ".join("row %d holds %s" % (
            p, classify(fin["plane"], p, fin["top"], K, rom, eff_to, eff_from)) for p in bad[:6])
        fails.append(f"{tag} FINAL: {len(bad)} of {K.PLANE_V_CELLS} plane rows do not hold the "
                     f"new blob's row for window top {fin['top']} — {shown}"
                     f"{'' if len(bad) <= 6 else ' (+%d more)' % (len(bad) - 6)}")
    else:
        print(f"  {tag} FINAL: all {K.PLANE_V_CELLS} plane rows hold blob $%06X at window "
              f"top {fin['top']}" % eff_to)


async def run_midsweep(rig, K, rom, button, start_at, row_from, row_to, eff_from, eff_to,
                       rows_from, rows_to, tag, fails):
    """A second pass over the SAME route, stopping mid-sweep to read the plane. Split from
    the pass above because reading 8 KB of VRAM every tick would make the walk unusable."""
    print(f"\n  ---- {tag}: mid-sweep read, same route ----")
    await rig.boot(start_at)
    for _ in range(SETTLE_TICKS):
        await rig.tick()
    walked = await walk(rig, button, lambda s: s["region"] == row_to["addr"], f"{tag}.w", K)
    await rig.hold(None)
    arm = walked[-1]
    if arm["cursor"] == 0:
        # A REAL RED, not a setup failure: no sweep armed, so there is no half-redrawn plane
        # and legs COVERED and VISIBLE have nothing to read. Reported as a FAIL because the
        # reason is the subject's absence, not the harness's.
        fails.append(f"{tag} COVERED/VISIBLE: no sweep armed on this route, so there is no "
                     f"half-redrawn plane to read. Both legs are unreached BECAUSE the "
                     f"feature is absent.")
        return
    # NOT a premise check against the EXPECTED arm value. That was tried and it was wrong:
    # leg ARM already grades the value, so a tree whose arm is merely WRONG (rather than
    # absent) aborted this pass at exit 2 and lost legs COVERED and VISIBLE — the gate got
    # QUIETER on a real defect. Found by mutation M3. All this pass needs is that a sweep
    # exists to read; whatever cursor it arms with, the covered set is derived from the two
    # tracker bytes and graded against the VDP.
    print(f"  {tag}: second pass armed at cursor {arm['cursor']}")

    for _ in range(K.VIS_TICKS):
        await rig.tick()
    s = await rig.sample(f"{tag}.vis", want_plane=True)
    print(fmt(s))
    if s["cursor"] == 0:
        raise GateError(f"{tag}: the sweep had already finished {K.VIS_TICKS} ticks after the "
                        f"arm, so there is no half-redrawn plane to grade. "
                        f"BG_WIPE_ROWS_PER_FRAME={K.WIPE_ROWS} against "
                        f"BG_SCREEN_ROWS={K.SCREEN_ROWS}: the deadline and the sweep length "
                        f"have converged and this leg can no longer fail.")

    cov = set(covered_rows(s, K))
    # ---- LEG COVERED: the tracker's account against the VDP ----
    lied = [p for p in sorted(cov)
            if classify_blob(s["plane"], p, K, rom, eff_to, rows_to,
                             eff_from, rows_from) != "new"]
    if lied:
        fails.append(f"{tag} COVERED: the tracker claims {len(cov)} plane rows drawn "
                     f"(BG_Wipe_Row={s['row']}, cursor={s['cursor']}), but {len(lied)} of them "
                     f"hold no row of blob $%06X at all: {lied[:8]}. The cursor advanced past "
                     f"rows the producer refused — the admitted-flag contract is broken."
                     % eff_to)
    else:
        print(f"  {tag} COVERED: all {len(cov)} rows the tracker claims are drawn hold a row "
              f"of blob $%06X" % eff_to)

    # ---- LEG VISIBLE: the design call of step 6 ----
    vrow_arm = arm["vscroll"] // K.ROW_PX
    vrow_now = s["vscroll"] // K.ROW_PX
    drift = vrow_now - vrow_arm
    vis = [(vrow_now + j) % K.PLANE_V_CELLS for j in range(K.SCREEN_ROWS)]
    missing = [p for p in vis if p not in cov]
    allowed = K.drift_allowance(K.VIS_TICKS, drift)
    print(f"  {tag} VISIBLE: {len(missing)} of {K.SCREEN_ROWS} visible plane rows un-swept "
          f"{K.VIS_TICKS} ticks after the arm; the scroll drifted {drift} row(s) over that "
          f"window, which allows {allowed}")
    if len(missing) > allowed:
        fails.append(f"{tag} VISIBLE: {len(missing)} of the {K.SCREEN_ROWS} plane rows the "
                     f"screen is showing are still un-swept {K.VIS_TICKS} ticks after the arm "
                     f"and only {allowed} are allowed by the {drift}-row scroll drift over "
                     f"that window: {missing[:8]}. Step 6's order exists so the rows the "
                     f"player is looking at clear the new-palette-over-old-art transient "
                     f"first; this is what §4.3's hidden-rows-first sweep, or a plain "
                     f"top-down walk from plane row 0, looks like from here.")

    # NON-VACUITY of both legs: something must still be UNSWEPT and still OLD, or "covered"
    # is the whole plane and neither leg asked a question.
    unswept = [p for p in range(K.PLANE_V_CELLS) if p not in cov]
    still_old = [p for p in unswept
                 if classify_blob(s["plane"], p, K, rom, eff_to, rows_to,
                                  eff_from, rows_from) == "old"]
    if not still_old:
        raise GateError(f"{tag}: not one of the {len(unswept)} un-swept plane rows still holds "
                        f"the OLD blob. Either the two blobs do not differ at those rows (the "
                        f"fixture cannot discriminate) or something repainted the plane "
                        f"synchronously, in which case this gate is not measuring a sweep.")
    print(f"  {tag} half-redrawn state confirmed: {len(cov)} swept, {len(unswept)} not, "
          f"{len(still_old)} of those still holding the OLD blob")


async def run_control(rig, K, rows, eff, start_at, row_from, row_to, button, fails):
    """A crossing whose two rows have the SAME effective layout must NOT arm a sweep.
    GREEN BEFORE STEP 6 AND GREEN AFTER, on purpose: it is the leg that catches a gate which
    has stopped being able to fail, and it is the leg that catches a wipe that fires on every
    region boundary in the act."""
    print(f"\n  ---- CONTROL: row {row_from['index']} -> row {row_to['index']}, same "
          f"effective layout $%06X, holding {button.upper()} ----" % eff)
    await rig.boot(start_at)
    for _ in range(SETTLE_TICKS):
        await rig.tick()
    s0 = await rig.sample("ctl.start")
    print(fmt(s0))
    if s0["region"] != row_from["addr"]:
        raise GateError("CONTROL: booting at %r resolved $%06X, not row %d at $%06X"
                        % (start_at, s0["region"], row_from["index"], row_from["addr"]))
    walked = await walk(rig, button, lambda s: s["region"] == row_to["addr"], "ctl", K)
    for _ in range(K.WIPE_FRAMES):
        await rig.tick()
        walked.append(await rig.sample("ctl.after"))
    print(fmt(walked[-1]))
    armed = [s for s in walked if s["cursor"] != 0]
    if armed:
        fails.append("CONTROL: crossing between two rows with the SAME effective layout "
                     "$%06X armed a sweep (cursor reached %d). Every region boundary in the "
                     "act would repaint the plane with the picture it already holds."
                     % (eff, max(s["cursor"] for s in armed)))
    else:
        print("  CONTROL: no sweep armed across %d ticks — correct" % len(walked))


# ---------------------------------------------------------------------------
def pick_fixture(rows, act_bg_layout, K):
    """The route, DERIVED from the region table in the ROM rather than typed."""
    def eff(r):
        return r["bg_layout"] or act_bg_layout

    tall = [r for r in rows if r["bg_layout"]]
    if len(tall) != 1:
        raise GateError(
            "this ROM has %d region rows naming their own rg_bg_layout, and this gate's route "
            "derivation assumes exactly one (the step-5 tall DEBUG row). Rows: %s. Either this "
            "is the RELEASE listing — in which case no crossing in the act changes the "
            "background and there is nothing here to measure — or a second layout has been "
            "authored and the route must be named explicitly."
            % (len(tall), [r["index"] for r in tall]))
    B = tall[0]
    y_mid = (B["y0"] + B["y1"]) // 2
    x_mid = (B["x0"] + B["x1"]) // 2
    left = region_table.region_at(rows, B["x0"] - 1, y_mid)
    above = region_table.region_at(rows, x_mid, B["y0"] - 1)
    for nm, r in (("left of", left), ("above", above)):
        if r is None:
            raise GateError(f"no region row lies {nm} row {B['index']} — the act's tiling "
                            f"proof says that cannot happen, so this is not the act table "
                            f"this gate thinks it is reading")
        if eff(r) == eff(B):
            raise GateError(f"the row {nm} row {B['index']} (row {r['index']}) has the SAME "
                            f"effective layout $%06X, so crossing that edge changes no "
                            f"background and the route cannot arm a sweep" % eff(B))
    # The CONTROL edge: two rows that share an effective layout and share a vertical edge.
    ctl = None
    for r in rows:
        if r is B or eff(r) != act_bg_layout:
            continue
        nb = region_table.region_at(rows, r["x1"] + 1, (r["y0"] + r["y1"]) // 2)
        if nb is not None and nb is not B and eff(nb) == act_bg_layout:
            ctl = (r, nb)
            break
    if ctl is None:
        raise GateError("no pair of adjacent region rows shares the act default layout, so "
                        "the CONTROL leg — the one that proves the sweep does NOT fire on "
                        "every crossing — has nothing to run on")
    return B, left, above, ctl, eff


async def run(rom_path, lst_path):
    rom = Path(rom_path).read_bytes()
    K = Consts(lst_path)
    print("GATE BG-WIPE — a crossing into a region with a different background must repaint it")
    print("  ROM  %s (%d bytes)" % (rom_path, len(rom)))
    print("  LST  %s" % lst_path)
    print("  derived: %s" % K.describe())
    print("  cross-checked against the listing's EQU block; SOURCE-ONLY (no EQU "
          "line exists, covered behaviourally by legs ARM/RATE): %s"
          % (", ".join(K.source_only) or "none"))

    sym = parse_lst(lst_path)
    for nm in ("GameState_OJZScroll_Init", "GameState_OJZScroll_Update", "Boot_At_X",
               "Boot_At_Y", "Boot_At_Flag", "Camera_X", "Camera_Y", "Region_Current",
               "BG_Plane_Layout", "BG_Plane_Top", "BG_Wipe_Cursor", "BG_Wipe_Row",
               "Parallax_Current_Vscroll_BG", "OJZ_Act1_Descriptor"):
        if nm not in sym:
            raise GateError("`%s` is not in %s — this is not the sonic4 DEBUG listing this "
                            "gate reads, and every sample would come from the wrong address"
                            % (nm, lst_path))
    rows = region_table.read_regions(rom, sym["OJZ_Act1_Descriptor"])
    act_off, _ = region_table.struct_layout("Act")
    act_bg = int.from_bytes(
        rom[sym["OJZ_Act1_Descriptor"] + act_off["act_bg_layout"]:
            sym["OJZ_Act1_Descriptor"] + act_off["act_bg_layout"] + 4], "big")
    B, left, above, (c0, c1), eff = pick_fixture(rows, act_bg, K)

    def rows_of(r):
        """The blob's height in map rows: its own span, or the plane's when it defaults."""
        return (r["bg_span"] // K.ROW_PX) if r["bg_span"] else K.PLANE_V_CELLS
    print("  act default layout $%06X" % act_bg)
    print("  subject row %d [x %d..%d, y %d..%d] layout $%06X span %d"
          % (B["index"], B["x0"], B["x1"], B["y0"], B["y1"], eff(B), B["bg_span"]))
    print("  from the LEFT : row %d, layout $%06X" % (left["index"], eff(left)))
    print("  from ABOVE    : row %d, layout $%06X" % (above["index"], eff(above)))
    print("  control edge  : row %d -> row %d, both $%06X" % (c0["index"], c1["index"], act_bg))

    # Routes, derived: start far enough inside the neighbour that the camera settles first.
    run_up = 8 * K.FLY
    y_mid = (B["y0"] + B["y1"]) // 2
    x_mid = (B["x0"] + B["x1"]) // 2
    h_start = (B["x0"] - run_up, y_mid)
    v_start = (x_mid, B["y0"] - run_up)
    ctl_start = (c0["x1"] - run_up, (c0["y0"] + c0["y1"]) // 2)

    inst = AetherInstance(rom_path, symbols=lst_path)
    try:
        sock = await asyncio.to_thread(inst.start)
    except (SpawnError, WrongServerError) as e:
        raise GateError(str(e)) from e
    b = BusClient(socket_path=sock, client_id="bgwipe", client_name="bg_wipe_gate")
    fails = []
    try:
        await b.connect()
        for m in ("emulator/step", "emulator/run_to", "emulator/hold", "emulator/release_all",
                  "emulator/read_vram", "emulator/read_memory", "emulator/write_memory",
                  "emulator/reset"):
            if not b.supports(m):
                raise GateError("the server does not advertise `%s`" % m)
        await _c(b, "emulator/load_symbols", {"path": lst_path})
        rig = Rig(b, sym, K, rom)

        await run_crossing(rig, K, rom, sym, "right", h_start, left, B, eff(left), eff(B),
                           "HORIZONTAL", fails)
        await run_midsweep(rig, K, rom, "right", h_start, left, B, eff(left), eff(B),
                           rows_of(left), rows_of(B), "HORIZONTAL", fails)
        await run_crossing(rig, K, rom, sym, "down", v_start, above, B, eff(above), eff(B),
                           "VERTICAL", fails)
        await run_control(rig, K, rows, act_bg, ctl_start, c0, c1, "right", fails)
    finally:
        await b.close()
        inst.reap()

    print()
    for f in fails:
        print("  FAIL  %s" % f)
    print("VERDICT: %s (%d failing legs)" % ("PASS" if not fails else "FAIL", len(fails)))
    if fails:
        raise Failure("%d legs red" % len(fails))


async def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default=str(AEON / "s4.debug.bin"))
    ap.add_argument("--lst", default=str(AEON / "s4.debug.lst"))
    a = ap.parse_args()
    try:
        await run(a.rom, a.lst)
    except GateError as e:
        print("COULD NOT RUN: %s" % e)
        return 2
    except Failure:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
