#!/usr/bin/env python3
"""GATE BG-PLANE-WINDOW — does a synchronous plane PRIME leave the window the scroll selects?

WHAT THIS EXISTS TO STOP, stated as the failure and not as the feature.

`Section_RedrawPlanes` is the engine's only synchronous Plane B writer (level init and the
DEBUG warp today; cache recovery when that path exists). Until this gate landed it blitted map
rows 0..63 of the region's background and re-seeded `BG_Plane_Top` to the constant 0, WHATEVER
the vertical scroll was. On every RELEASE row that is a no-op — the act's background map is
exactly the plane's height, so rows 0..63 ARE the whole map and 0 IS the only window. On a map
TALLER than the plane (regions part 2 step 5's DEBUG fixture) with the scroll away from the
top, it leaves the plane holding the WRONG 64 rows, and `BG_Stream_Update` can only walk that
back at BG_STREAM_MAX_ROWS = 2 rows a frame.

WHY THE EXISTING ROM-SIDE GATE CANNOT SEE IT. `tools/test_bg_tall_map.py` reads region rows,
blob bytes, the resolved parallax mapping and call encodings — and NOT ONE of its legs observes
the VDP. A build that computes a window and writes it to the wrong VRAM address passes all of
them, and so does a build that computes no window at all. This gate boots a headless
`oracle-aether`, drives the DEBUG warp mailbox, and reads `BG_Plane_Top` and the live Plane B
nametable out of the machine.

THE SHAPE OF THE MEASUREMENT, and why the SECOND warp is the subject.

A warp from a LOW scroll cannot discriminate and this gate does not pretend otherwise. The
rate clamp (`BG_VSCROLL_MAX_STEP`, 16 px = 2 rows a frame) walks the scroll up from wherever it
was, and `BG_Stream_Update`'s budget is DERIVED from that same clamp — so a plane primed to
row 0 while the scroll is also near 0 stays correct all the way up. The defect needs the scroll
to be HIGH at the instant of the prime. So:

  warp 1  -> deep inside the tall region; run until the scroll settles at its region-derived
             ceiling. This is the CONTROL: the steady-state tracker is asserted correct here,
             so a red below is about the prime and not about the reader.
  warp 2  -> a DIFFERENT point in the SAME region, so the scroll's target is unchanged and the
             rate clamp holds it at the ceiling across the prime. Sample AT THE ACK.

Every expectation is computed from state read out of the machine at the sampling instant
(`Parallax_Current_Vscroll_BG`, `Region_Current` -> `rg_bg_span`, `BG_Plane_Layout`) against
constants parsed out of the engine's own sources. NOTHING here is copied from a table in
`docs/DEFERRED_WORK.md`: that table was measured stale at exactly this spot (its region extent
and its ceiling-binds-at camera Y were both corrected by the parcel that wrote this file).

WHAT A GREEN HERE DOES NOT SAY. It says nothing about the BOOT prime beyond `BG_Plane_Top == 0`
and the act blob's first 64 rows being in the plane, because at boot the correct window IS 0 —
`Parallax_Init` zeroes the scroll and the rate clamp caps the first frames, so boot cannot
produce a non-zero window to check. It says nothing about the parallax BAND rates, which alias
in this very region (BG-BAND-PLANE-ANCHOR, deliberately open — the nametable is correct there
and this gate reads the nametable). And it samples two scroll values, not the traversal: the
full BG-TALL leg-2 sweep is a separate, foreground procedure.

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
BOOT_FRAMES = 120
ACK_FRAMES = 240               # generous; the ack is polled, not budgeted
SETTLE_FRAMES = 180            # the scroll ratchets at BG_VSCROLL_MAX_STEP px a frame


class GateError(RuntimeError):
    """A premise this gate refuses to measure past — exit 2, never a pass."""


class Failure(RuntimeError):
    """A real red — exit 1."""


# ---------------------------------------------------------------------------
# The constants, each re-derived from the source that declares it.
# ---------------------------------------------------------------------------
def _const(rel, name):
    text = (AEON / rel).read_text(errors="replace")
    m = re.search(rf"^\s*pub\s+const\s+{re.escape(name)}\s*=\s*(\d+)\s*(?://|$)",
                  text, re.M)
    if not m:
        raise GateError(
            f"{rel} no longer declares `pub const {name} = <int>`. Every expectation in "
            f"tools/bg_window_gate.py is derived from it, so this is a SETUP FAILURE and "
            f"must not be defaulted to a remembered value.")
    return int(m.group(1))


class Consts:
    def __init__(self, lst):
        self.PLANE_H_CELLS = _const("engine/system/constants.emp", "PLANE_H_CELLS")
        self.PLANE_V_CELLS = _const("engine/system/constants.emp", "PLANE_V_CELLS")
        self.SCREEN_HEIGHT = _const("engine/system/constants.emp", "SCREEN_HEIGHT")
        self.PLANE_B_CELL_ROWS = _const("engine/level/parallax.emp", "PLANE_B_CELL_ROWS")
        self.MAX_STEP_ROWS = _const("engine/level/parallax.emp", "BG_VSCROLL_MAX_STEP_ROWS")
        # engine/level/parallax.emp: PLANE_B_SPAN = PLANE_B_CELL_ROWS * 8
        self.PLANE_B_SPAN = self.PLANE_B_CELL_ROWS * 8
        # engine/level/parallax.emp: BG_VSCROLL_ROW_PX = PLANE_B_SPAN / PLANE_B_CELL_ROWS
        self.ROW_PX = self.PLANE_B_SPAN // self.PLANE_B_CELL_ROWS
        # engine/level/bg.emp: BG_SCREEN_ROWS = SCREEN_HEIGHT / BG_STREAM_ROW_PX + 1
        self.SCREEN_ROWS = self.SCREEN_HEIGHT // self.ROW_PX + 1
        # engine/level/bg.emp: BG_STREAM_SPARE_ROWS / BG_STREAM_LEAD_ROWS
        self.SPARE_ROWS = self.PLANE_V_CELLS - self.SCREEN_ROWS
        self.LEAD = self.SPARE_ROWS // 2
        # engine/level/bg.emp: BG_STREAM_MAX_ROWS = BG_VSCROLL_MAX_STEP / BG_STREAM_ROW_PX
        self.MAX_ROWS = self.MAX_STEP_ROWS
        self.ROW_BYTES = self.PLANE_H_CELLS * 2
        self.PLANE_BYTES = self.ROW_BYTES * self.PLANE_V_CELLS

        # TWO NAMESPACES, ONE INTERFACE. The listing carries `EQU PLANE_V_CELLS = $...`;
        # cross-check the parsed source against the BUILT artifact rather than trusting the
        # parse alone. A disagreement means the .emp this gate read is not the .emp that
        # produced the ROM it is about to grade.
        m = re.search(r"^EQU\s+PLANE_V_CELLS\s*=\s*\$([0-9A-Fa-f]+)\s*$",
                      Path(lst).read_text(errors="replace"), re.M)
        if m and int(m.group(1), 16) != self.PLANE_V_CELLS:
            raise GateError(
                f"PLANE_V_CELLS is {self.PLANE_V_CELLS} in engine/system/constants.emp but "
                f"${m.group(1)} = {int(m.group(1), 16)} in {lst}. The source tree and the "
                f"built listing disagree — this gate would grade one against the other's "
                f"arithmetic.")
        self.lst_confirmed_plane_v = bool(m)

        # The engine spells the px->row conversion as `lsr.w #3` in BOTH
        # BG_Stream_Update and Section_RedrawPlanes. If the row height ever stops being 8
        # the Python below would silently model a shift the 68000 does not perform.
        if self.ROW_PX != 8:
            raise GateError(
                f"BG_VSCROLL_ROW_PX derives to {self.ROW_PX}, not 8, but the engine spells "
                f"the pixel->row conversion as a literal `lsr.w #3`. The model in this gate "
                f"and the code it grades have diverged.")

    def want_top(self, vscroll, span):
        """engine/level/bg.emp's window rule, restated:
             want_top = clamp((vscroll >> 3) - LEAD, 0, map_rows - PLANE_V_CELLS)
           `span` 0 means the act default, whose map is the plane."""
        map_rows = (span // self.ROW_PX) if span else self.PLANE_V_CELLS
        max_top = max(0, map_rows - self.PLANE_V_CELLS)
        t = (vscroll // self.ROW_PX) - self.LEAD
        return max(0, min(max_top, t)), max_top, map_rows

    def describe(self):
        return (f"PLANE {self.PLANE_H_CELLS}x{self.PLANE_V_CELLS} cells, row {self.ROW_BYTES} B; "
                f"SCREEN_HEIGHT {self.SCREEN_HEIGHT} -> {self.SCREEN_ROWS} touchable rows; "
                f"spare {self.SPARE_ROWS}, LEAD {self.LEAD}; rate {self.MAX_STEP_ROWS} rows/frame")


# ---------------------------------------------------------------------------
# Bus helpers
# ---------------------------------------------------------------------------
async def _c(b, method, params=None, timeout=180.0):
    return await asyncio.wait_for(b.call(method, params or {}), timeout=timeout)


async def rd(b, addr, width):
    return int(await read_bytes(b, addr, width), 16)


def s16(v):
    return v - 0x10000 if v >= 0x8000 else v


async def read_plane_b(b, nbytes):
    out = bytearray()
    for off in range(0, nbytes, 4096):
        n = min(4096, nbytes - off)
        r = await _c(b, "emulator/read_vram",
                     {"addr": hex(VRAM_PLANE_B + off), "len": n})
        h = unprefix(r["bytes"])
        if len(h) != n * 2:
            raise GateError("short VRAM read at +%d: %d hex chars, wanted %d"
                            % (off, len(h), n * 2))
        out += bytes.fromhex(h)
    return bytes(out)


async def warp(b, sym, x, y):
    """The DEBUG warp mailbox (games/sonic4/config/ram.emp): X, Y, then the FLAG last —
    the write order IS the protocol. The ack is POLLED: a budgeted wait would let a warp
    that never happened be sampled as if it had."""
    for nm, v, w in (("Warp_Req_X", x, 2), ("Warp_Req_Y", y, 2), ("Warp_Req_Flag", 1, 1)):
        await _c(b, "emulator/write_memory", {"addr": hex(sym[nm]), "value": v, "width": w})
    for i in range(ACK_FRAMES):
        await _c(b, "emulator/run_frames", {"frames": 1})
        if await rd(b, sym["Warp_Req_Flag"], 1) == 0:
            return i + 1
    raise GateError("Warp_Req_Flag never cleared in %d frames — the teleport did not happen, "
                    "so every sample after it would be the sample before it" % ACK_FRAMES)


# ---------------------------------------------------------------------------
async def sample(b, sym, K, rom, want_plane=True):
    """Everything the expectations are derived FROM, read at one instant."""
    s = {}
    s["cam"] = ((await rd(b, sym["Camera_X"], 4)) >> 16,
                (await rd(b, sym["Camera_Y"], 4)) >> 16)
    s["vscroll"] = s16(await rd(b, sym["Parallax_Current_Vscroll_BG"], 2))
    s["top"] = await rd(b, sym["BG_Plane_Top"], 2)
    s["layout"] = await rd(b, sym["BG_Plane_Layout"], 4)
    s["region"] = await rd(b, sym["Region_Current"], 4)
    off, _size = region_table.struct_layout("Region")
    if s["region"]:
        at = s["region"] + off["rg_bg_span"]
        if at + 2 > len(rom):
            raise GateError("Region_Current = $%06X is not a ROM address in this image "
                            "(%d bytes)" % (s["region"], len(rom)))
        s["span"] = int.from_bytes(rom[at:at + 2], "big")
    else:
        s["span"] = 0
    s["want"], s["max_top"], s["map_rows"] = K.want_top(s["vscroll"], s["span"])
    if want_plane:
        s["plane"] = await read_plane_b(b, K.PLANE_BYTES)
    return s


def fmt(tag, s):
    return ("  %-14s cam=%s vscroll=%d  BG_Plane_Top=%d  want_top=%d  "
            "span=%d (%d rows, max_top=%d)  layout=$%06X"
            % (tag, s["cam"], s["vscroll"], s["top"], s["want"], s["span"],
               s["map_rows"], s["max_top"], s["layout"]))


def check_plane(s, rom, K, label, fails):
    """Every plane row must hold the map row the window names.

    The plane is a ring: map row m is shown by plane row m mod PLANE_V_CELLS. So with the
    window at `top`, plane row (m & 63) must equal map row m of the blob at BG_Plane_Layout,
    for every m in [top, top+63]. The step-5 fixture's 96 rows are PAIRWISE DISTINCT by
    construction (tools/gen_tall_bg_test.py asserts it), which is the only reason a row
    comparison can say WHICH map row a plane row holds."""
    base = s["layout"]
    need = (s["want"] + K.PLANE_V_CELLS) * K.ROW_BYTES
    if base == 0 or base + need > len(rom):
        fails.append("%s: BG_Plane_Layout=$%06X cannot supply map rows [%d, %d] out of a "
                     "%d-byte ROM — the pointer, not the window, is wrong"
                     % (label, base, s["want"], s["want"] + K.PLANE_V_CELLS - 1, len(rom)))
        return
    bad = []
    for m in range(s["want"], s["want"] + K.PLANE_V_CELLS):
        p = m % K.PLANE_V_CELLS
        got = s["plane"][p * K.ROW_BYTES:(p + 1) * K.ROW_BYTES]
        expect = rom[base + m * K.ROW_BYTES: base + (m + 1) * K.ROW_BYTES]
        if got != expect:
            # WHICH map row IS it holding? The fixture's rows are pairwise distinct, so
            # this identifies the actual window rather than only reporting a mismatch.
            held = [n for n in range(s["map_rows"])
                    if rom[base + n * K.ROW_BYTES: base + (n + 1) * K.ROW_BYTES] == got]
            bad.append((p, m, held))
    if bad:
        shown = ", ".join("plane row %d holds map row %s, wanted %d"
                          % (p, held if held else "<none of the map>", m)
                          for p, m, held in bad[:4])
        fails.append("%s: %d of %d plane rows hold the wrong map row. Window claimed "
                     "[%d, %d]. %s%s"
                     % (label, len(bad), K.PLANE_V_CELLS, s["want"],
                        s["want"] + K.PLANE_V_CELLS - 1, shown,
                        "" if len(bad) <= 4 else " (+%d more)" % (len(bad) - 4)))


async def run(rom_path, lst_path, w1, w2):
    rom = Path(rom_path).read_bytes()
    K = Consts(lst_path)
    print("GATE BG-PLANE-WINDOW — a synchronous prime must leave the window the scroll selects")
    print("  ROM  %s (%d bytes)" % (rom_path, len(rom)))
    print("  LST  %s" % lst_path)
    print("  derived: %s" % K.describe())
    print("  (PLANE_V_CELLS cross-checked against the listing's own EQU: %s)"
          % ("yes" if K.lst_confirmed_plane_v else "NO EQU LINE FOUND"))

    inst = AetherInstance(rom_path, symbols=lst_path)
    try:
        sock = await asyncio.to_thread(inst.start)
    except (SpawnError, WrongServerError) as e:
        raise GateError(str(e)) from e
    b = BusClient(sock, client_id="bgwin", client_name="bg_window_gate")
    await b.connect()
    fails = []
    try:
        for m in ("emulator/read_vram", "emulator/run_frames",
                  "emulator/read_memory", "emulator/write_memory"):
            if not b.supports(m):
                raise GateError("the server does not advertise `%s`" % m)
        sym = parse_lst(lst_path)
        for nm in ("Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag", "Camera_X", "Camera_Y",
                   "Parallax_Current_Vscroll_BG", "BG_Plane_Top", "BG_Plane_Layout",
                   "Region_Current"):
            if nm not in sym:
                raise GateError("`%s` is not in %s — this is not the DEBUG listing this "
                                "gate reads, and every sample below would be read from the "
                                "wrong address" % (nm, lst_path))

        # ---- LEG 0: the BOOT prime. The correct window at boot IS 0 (Parallax_Init
        #      zeroes the scroll and the rate clamp caps the first frames), so this is a
        #      REGRESSION leg: a windowed prime must not move it. ----
        await _c(b, "emulator/run_frames", {"frames": BOOT_FRAMES})
        boot = await sample(b, sym, K, rom)
        print(fmt("boot", boot))
        if boot["top"] != boot["want"]:
            fails.append("boot: BG_Plane_Top=%d but the scroll %d selects window top %d"
                         % (boot["top"], boot["vscroll"], boot["want"]))
        check_plane(boot, rom, K, "boot", fails)

        # ---- warp 1: into the tall region, then settle. THE CONTROL. ----
        n = await warp(b, sym, *w1)
        print("  warp 1 -> %r acked in %d frames" % (w1, n))
        await _c(b, "emulator/run_frames", {"frames": SETTLE_FRAMES})
        ctl = await sample(b, sym, K, rom)
        print(fmt("settled", ctl))

        # NON-VACUITY, refused rather than reported green. Three things must be true or
        # this gate is measuring the shipped release shape in disguise.
        if ctl["span"] <= K.PLANE_B_SPAN:
            raise GateError(
                "the region under the camera after warp 1 declares rg_bg_span=%d, which is "
                "not taller than the plane (%d). With a map no taller than the plane the "
                "window has ONE position and this gate cannot tell a windowed prime from a "
                "row-0 one. Aim warp 1 inside the tall DEBUG region."
                % (ctl["span"], K.PLANE_B_SPAN))
        if ctl["want"] == 0:
            raise GateError(
                "the settled scroll is %d, which selects window top 0 — the same value the "
                "UNFIXED code writes unconditionally. This gate would pass on the defect. "
                "The scroll must reach at least %d px for a non-zero window."
                % (ctl["vscroll"], (K.LEAD + 1) * K.ROW_PX))
        if ctl["top"] != ctl["want"]:
            fails.append("CONTROL: after settling, BG_Plane_Top=%d but the scroll %d selects "
                         "%d. The steady-state tracker is wrong, so nothing below is about "
                         "the prime." % (ctl["top"], ctl["vscroll"], ctl["want"]))
        check_plane(ctl, rom, K, "CONTROL settled", fails)

        # ---- warp 2: the SUBJECT. Same region, so the scroll's target does not move and
        #      the rate clamp holds it at the ceiling across the prime. ----
        n = await warp(b, sym, *w2)
        print("  warp 2 -> %r acked in %d frames" % (w2, n))
        sub = await sample(b, sym, K, rom)
        print(fmt("at the prime", sub))
        if sub["cam"] == ctl["cam"]:
            raise GateError("the camera is at %r before AND after warp 2 — the subject "
                            "sample is the control sample again" % (ctl["cam"],))
        if sub["span"] <= K.PLANE_B_SPAN:
            raise GateError("warp 2 landed outside the tall region (rg_bg_span=%d); the "
                            "prime it triggered had one legal window" % sub["span"])
        if sub["want"] == 0:
            raise GateError("the scroll at warp 2's prime is %d, which selects window top 0 "
                            "— indistinguishable from the unfixed constant" % sub["vscroll"])

        # LEG 1 — THE SEED.
        if sub["top"] != sub["want"]:
            fails.append(
                "SEED: at warp 2's prime BG_Plane_Top=%d, but the live scroll %d selects "
                "window top %d. The prime re-seeded the tracker to a value the scroll does "
                "not select; BG_Stream_Update can only walk that back at %d rows a frame "
                "(%d frames from here)."
                % (sub["top"], sub["vscroll"], sub["want"], K.MAX_ROWS,
                   -(-abs(sub["want"] - sub["top"]) // K.MAX_ROWS)))
        # LEG 2 — THE PICTURE.
        check_plane(sub, rom, K, "PICTURE at the prime", fails)

        # LEG 3 — and the tracker still names what the plane holds afterwards, so the
        # window the prime wrote is one the steady state agrees with rather than one it
        # immediately walks away from.
        await _c(b, "emulator/run_frames", {"frames": 4})
        after = await sample(b, sym, K, rom)
        print(fmt("prime + 4", after))
        if after["top"] != after["want"]:
            fails.append("prime+4: BG_Plane_Top=%d, scroll %d selects %d"
                         % (after["top"], after["vscroll"], after["want"]))
        check_plane(after, rom, K, "prime + 4", fails)
    finally:
        await b.close()
        inst.reap()

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
    # Both points sit inside the step-5 tall DEBUG region (act 1 row 11) at a Y whose
    # camera drives the BG scroll to that region's ceiling. They are ARGUMENTS, and the
    # gate refuses above rather than passing if either lands outside it.
    ap.add_argument("--warp1", default="5600,5100")
    ap.add_argument("--warp2", default="5300,5800")
    a = ap.parse_args()
    w1 = tuple(int(v) for v in a.warp1.split(","))
    w2 = tuple(int(v) for v in a.warp2.split(","))
    try:
        await run(a.rom, a.lst, w1, w2)
    except GateError as e:
        print("COULD NOT RUN: %s" % e)
        return 2
    except Failure:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
