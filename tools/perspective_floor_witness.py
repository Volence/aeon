#!/usr/bin/env python3
"""perspective_floor_witness — does the RUNNING ROM carry the fan, and where is
the camera when the owner looks at it?

Everything else about this floor is checked without booting anything:
tools/test_perspective_floor.py scores the generator's pixels, the committed
override, the BAKED artifacts and the scene's ramp window. All of that can be
perfectly self-consistent while the ROM shows something else — and the failure
mode of a subject that is not really there is a CLEAN result, not a red one. So
this instrument boots the ROM, walks the effects lab to the floor row, and reads
back the two things that decide what the VDP fetches:

  * THE LIVE PLANE-B NAMETABLE at $E000, against `zone_bg.bin`.
  * THE LIVE VRAM TILES those cells address, against the generator's own pixels.

Both are exact byte comparisons against the running machine.

IT ALSO REPORTS THE CAMERA, and that turned out to be the finding worth having:
the lab chord that selects this scene is START+RIGHT x20, and RIGHT is a
direction as well as a hotkey, so SELECTING THE ROW LEAVES THE CAMERA AT x 736.
The floor's clean camera range is 192/F px, F being the scene's curve end factor
(perspective_floor_gen's header derives it), so at FACTOR_1_4 the owner would
arrive 32 px inside the edge — which is why the scene ships FACTOR_1_8. That
number could not have come from any check that did not boot the ROM.

WHAT THIS DOES *NOT* MEASURE, stated so the absence is not mistaken for a pass:
THE ON-SCREEN SEAM GEOMETRY. Scoring beams off `emulator/scanlines` was tried
and is booked as NOT MEASURED, for reasons that are themselves measured:

  * Scene 20 renders the floor band under VDP shadow/highlight and the mask
    VARIES ALONG A ROW, so a luma detector reads the shadow boundaries as seams
    — measured, it called 58% of one row "dark" and the row was then discarded
    for being too dark to hold seams.
  * Masking Plane A to remove the foreground occluder is WORSE, not better:
    with any layer masked this server answers `scanlines` with
    source="stateRender", a post-hoc render from end-of-frame VDP state, which
    cannot witness a per-line HScroll ramp at all. It would fail by showing a
    clean picture.
  * Inverting the shadow mask by colour was tried against the RUNTIME CRAM
    (read back and confirmed identical to ojz_palette.bin) and did not close:
    the observed band colours (#482424, #241212, #362424, #6D4848) do not fall
    out of shadow = v/2, shadow = (3-bit v)>>1, or highlight = v*1.5 applied to
    the ramp the VRAM tiles actually use (palette 4/5/6 = #904824 / #B46C24 /
    #D89048, read back below). Until that arithmetic is pinned against this
    emulator, a seam count taken from those pixels is a number with no referent.

The composited geometry IS checked on the same art, in
test_perspective_floor.py's `test_composited_beams_converge_on_the_screen_centre
_column` — through curve_probe's transcription of the engine's own per-line ramp
rather than through the VDP. That is a MODEL of the scroll and is labelled as
one.

    python3 tools/perspective_floor_witness.py --rom s4.debug.bin
"""
import argparse
import asyncio
import struct
import sys
from pathlib import Path

AEON = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from suite_paths import add_client_path  # noqa: E402
add_client_path()
sys.path.insert(0, str(AEON / "tools"))

from aether import BusClient            # noqa: E402
from aether_instance import (            # noqa: E402
    AetherInstance, SpawnError, WrongServerError, read_bytes, unprefix)
import perspective_floor_gen as pfg      # noqa: E402

LAB_ROW = 20                 # Scene_Perspective_Floor's registry index
HOLD_FRAMES = 2              # preset_lab_witness measured that a one-frame hold
RELEASE_FRAMES = 2           # can be swallowed by a lag frame
PRESS_RETRIES = 3
BOOT_FRAMES = 240
VRAM_PLANE_B = 0xE000        # engine/system/constants.emp VRAM_PLANE_B
NT_PATH = "games/sonic4/data/generated/ojz/act1/zone_bg.bin"
SHIPPED_END_FACTOR = 0.125   # the scene's To(FACTOR_1_8)


class WitnessError(RuntimeError):
    pass


async def _c(b, method, params=None, timeout=180.0):
    return await asyncio.wait_for(b.call(method, params or {}), timeout=timeout)


def lst_symbol(lst_path, name):
    """One symbol's address out of the listing's own address table.

    The table's lines read " NAME : ADDR C |". Matching the DISASSEMBLY column
    instead (the form this file first used) finds nothing for a RAM label — RAM
    labels have no code line — and the instrument then reported "not in the
    .lst" for a symbol that is on line 6082 of it.
    """
    tail = " %s : " % name
    for line in open(lst_path, encoding="utf-8", errors="replace"):
        if line.startswith(tail):
            return int(line.split(" : ", 1)[1].split()[0], 16) & 0xFFFFFF
    return None


async def press_right_chord(b):
    r = await _c(b, "emulator/play_input",
                 {"rows": [{"start": 0, "end": HOLD_FRAMES,
                            "buttons": ["start", "right"], "port": 0}]})
    if int(r.get("frames", -1)) != HOLD_FRAMES:
        raise WitnessError("play_input advanced %s frames, wanted %d"
                           % (r.get("frames"), HOLD_FRAMES))
    await _c(b, "emulator/run_frames", {"frames": RELEASE_FRAMES})


async def read_words(b, addr, count):
    r = await _c(b, "emulator/read_vram", {"addr": hex(addr), "len": count * 2})
    h = unprefix(r["bytes"])
    return [int(h[i:i + 4], 16) for i in range(0, len(h), 4)]


async def read_tile(b, idx):
    r = await _c(b, "emulator/read_vram", {"addr": hex(idx * 32), "len": 32})
    h = unprefix(r["bytes"])
    out = []
    for i in range(0, len(h), 2):
        v = int(h[i:i + 2], 16)
        out.append((v >> 4) & 15)
        out.append(v & 15)
    return out


async def settle_transition(client, lst_path, limit=None):
    """Run the machine one frame at a time until the parallax crossfade has FINISHED.

    WHY THIS EXISTS (CURSOR-RACE-SWEEP, 2026-09-18). A lab-cursor step and a section
    boundary crossing both route into `Parallax_StartTransition`, which stages
    `Parallax_Target_Config` and sets `Parallax_Transition_Frames` to
    PARALLAX_TRANS_DEFAULT; `Parallax_Update` promotes Target into Current only when that
    counter reaches 0. Anything read inside that window — the per-line HScroll table, the
    band scroll accumulators, VSRAM, the pixels — is a LERP between two scenes.

    SETTLE THE MACHINE, DO NOT MODEL IT. The condition below is the engine's own counter,
    read out of the running machine one frame at a time. The BOUND is the engine's own
    PARALLAX_TRANS_DEFAULT via `fg_left_edge_gate._trans_default()` — the tree's one
    derivation of it, imported rather than re-derived, so there is no second copy to go
    stale. Restating `Parallax_Active_Config`'s `Frames != 0 -> Target` rule in Python was
    considered and rejected for the gate and is rejected here for the same two reasons: a
    second copy of an engine rule in a tool is a stale-green waiting to happen, and it
    would fix only which record you name, not the lerped values you read.

    LOUD ON UNMEASURABLE: a counter that never reaches 0 raises, because "the transition
    never completed" and "we gave up early" deserve different verdicts and neither is a
    quiet continue.

    ⚠ DO NOT "TIDY" THIS INTO fg_left_edge_gate.settle_transition. THREE functions in
    tools/ have this name and the duplication is deliberate in two of the three cases —
    what must have ONE home is the engine RULE, and it does: PARALLAX_TRANS_DEFAULT is
    read by `fg_left_edge_gate._trans_default()` and by nothing else, which all three
    bounds either call or should.

      * `fg_left_edge_gate.settle_transition(c, syms)` takes a PRE-RESOLVED `syms` dict
        built from `emulator/lookup_symbol` calls over a bare `BusClient`.
      * THIS one takes a `.lst` PATH, because the floor family — this file, floor_capture
        and floor_hscroll_dump — never calls `lookup_symbol` at all: it parses the listing
        with `lst_symbol()`, and it calls through `_c()`, the asyncio.wait_for timeout
        wrapper, rather than `b.call` directly. Collapsing the two would mean teaching the
        attested gate's version to accept either a resolved address or a resolver, i.e.
        adding a parameter to a function on the gate's hot path to serve a caller that
        does not exist yet. The plumbing is what differs; the rule is not duplicated.
      * `left_edge_vsram_probe.settle_transition(c, syms, limit=300)` is the THIRD, and it
        is the one genuinely worth collapsing: same signature as the gate's, but its bound
        is a magic 300 rather than a derivation, so it is the only one of the three whose
        loudness threshold would not move with the constant. It waits on the machine's own
        counter, so it is CORRECT — the bound governs only how it reports an unmeasurable
        — and it was left alone by CURSOR-RACE-SWEEP because that parcel fixed only what it
        measured wrong. Named here rather than left for someone to rediscover.

    Returns the number of frames waited (0 when nothing was in flight).
    """
    import fg_left_edge_gate as _G          # local: the one PARALLAX_TRANS_DEFAULT reader
    budget = limit if limit is not None else 2 * _G._trans_default()
    sym = lst_symbol(lst_path, "Parallax_Transition_Frames")
    if sym is None:
        raise WitnessError(
            "Parallax_Transition_Frames is not in %s, so this tool cannot tell a settled "
            "frame from a crossfade and would read a lerp between two scenes without "
            "knowing it" % lst_path)
    for waited in range(budget + 1):
        if int((await read_bytes(client, sym, 1))[:2], 16) == 0:
            return waited
        await _c(client, "emulator/run_frames", {"frames": 1})
    raise WitnessError(
        "Parallax_Transition_Frames never reached 0 in %d frames (2 x "
        "PARALLAX_TRANS_DEFAULT, derived from engine/system/constants.emp) — the staged "
        "transition is not completing, so nothing read here is a settled scene" % budget)


async def walk_to_floor_row(client, lab_sym):
    got = -1
    for want in range(1, LAB_ROW + 1):
        for _ in range(PRESS_RETRIES):
            await press_right_chord(client)
            got = int((await read_bytes(client, lab_sym, 1))[:2], 16)
            if got == want:
                break
        else:
            raise WitnessError("the lab cursor stuck at %d walking to row %d"
                               % (got, want))
    if got != LAB_ROW:
        raise WitnessError("lab cursor is %d, wanted %d" % (got, LAB_ROW))
    return got


async def run(rom, lst):
    inst = AetherInstance(rom)
    try:
        sock = await asyncio.to_thread(inst.start)
    except (SpawnError, WrongServerError) as e:
        raise WitnessError(str(e)) from e
    client = BusClient(sock, client_id="pfloor",
                       client_name="perspective_floor_witness")
    await client.connect()
    ok = True
    try:
        for m in ("emulator/read_vram", "emulator/play_input",
                  "emulator/run_frames", "emulator/read_memory"):
            if not client.supports(m):
                raise WitnessError("the server does not advertise `%s`" % m)
        await _c(client, "emulator/run_frames", {"frames": BOOT_FRAMES})

        lab_sym = lst_symbol(lst, "Debug_Lab_Index")
        cam_sym = lst_symbol(lst, "Camera_X")
        if lab_sym is None:
            raise WitnessError("Debug_Lab_Index is not in %s; the lab cursor "
                               "cannot be verified and this run would be "
                               "walking blind" % lst)
        row = await walk_to_floor_row(client, lab_sym)
        print("  lab cursor row %d  (START+RIGHT x%d from row 0)" % (row, LAB_ROW))
        await _c(client, "emulator/run_frames", {"frames": 30})
        # ---- AND THEN SETTLE, WHICH IS A BACKSTOP AND NOT A WAIT ----
        # The 30 above stays: it is not only about the crossfade, it is also "let the
        # scene's art and the glyph DMAs land", and shortening it would change what the
        # comparisons below read. What it is NOT is coupled to anything. It exceeds
        # PARALLAX_TRANS_DEFAULT (16) today by arithmetic that happens to hold, and the
        # day that constant goes above 30 this tool starts reading a crossfade again with
        # nothing going red — which is precisely the class the CURSOR-RACE-SWEEP parcel
        # exists to close, so leaving the derived-bound helper unused twelve lines above
        # this call was the accident, not the design.
        #
        # ORDER IS THE POINT: settling AFTER the 30 makes the behaviour change provably
        # ZERO while 30 >= PARALLAX_TRANS_DEFAULT (the counter is already 0, so this
        # returns immediately and runs no frames), and makes the tool correct rather than
        # lucky if it ever is not. The printed count is the per-run EVIDENCE that the 30
        # was enough: a `settled after 0 frame(s)` line is the arithmetic being checked
        # against the machine on every run instead of being trusted.
        waited = await settle_transition(client, lst)
        print("  settled after %d frame(s) (Parallax_Transition_Frames == 0) — %s"
              % (waited,
                 "the 30 above confirmed sufficient by the machine, not assumed"
                 if waited == 0 else
                 "THE 30 ABOVE WAS NOT ENOUGH; this wait is what kept the read off a "
                 "crossfade, and the literal should be revisited"))

        # Camera_X is u32 16.16 (engine/ram.emp), so the top word is the integer
        # part. Reading four bytes and taking the whole longword would report the
        # position multiplied by 65536.
        if cam_sym is None:
            print("  camera: Camera_X is not in the .lst — NOT REPORTED")
        else:
            cam = int(await read_bytes(client, cam_sym, 2), 16)
            clean = pfg.clean_camera_range(SHIPPED_END_FACTOR)
            print("  camera after that walk: x %d  (the chord's RIGHT is a "
                  "direction as well as a hotkey)" % cam)
            print("     clean camera range at the shipped curve end factor: "
                  "%.0f px" % clean)
            if cam >= clean:
                print("     FAIL  the chord lands the camera PAST the clean "
                      "range, so the wrap's next apex is on screen before he "
                      "has moved at all")
                ok = False

        # ---- the live plane against the baked nametable ----
        nt = open(NT_PATH, "rb").read()
        s = pfg.SHIPPED
        live_rows = {}
        bad = 0
        for row_i in range(s["row0"], s["row1"] + 1):
            live = await read_words(client,
                                    VRAM_PLANE_B + row_i * pfg.PLANE_COLS * 2,
                                    pfg.PLANE_COLS)
            live_rows[row_i] = live
            # zone_bg.bin is ROW-major since regions part 2 step 2 — the blob's
            # order IS the nametable's, so a plane row is one contiguous run.
            want = [struct.unpack_from(">H", nt,
                                       (row_i * pfg.PLANE_COLS + col) * 2)[0]
                    for col in range(pfg.PLANE_COLS)]
            bad += sum(1 for a, b in zip(live, want) if a != b)
        total_words = (s["row1"] + 1 - s["row0"]) * pfg.PLANE_COLS
        if bad:
            print("  FAIL  %d of %d live Plane-B nametable words differ from "
                  "zone_bg.bin" % (bad, total_words))
            ok = False
        else:
            print("  PASS  live Plane-B nametable rows %d..%d byte-identical to "
                  "zone_bg.bin (%d words)"
                  % (s["row0"], s["row1"], total_words))

        # ---- the live tiles those cells address, against the art ----
        art, rows, _shade, _span = pfg.shipped_band()
        cache, mismatch, checked = {}, 0, 0
        for ri, row_i in enumerate(rows):
            for col, w in enumerate(live_rows[row_i]):
                idx = w & 0x7FF
                if idx not in cache:
                    cache[idx] = await read_tile(client, idx)
                t = cache[idx]
                for iy in range(8):
                    sy = 7 - iy if (w >> 12) & 1 else iy
                    for ix in range(8):
                        sx = 7 - ix if (w >> 11) & 1 else ix
                        checked += 1
                        if t[sy * 8 + sx] != art[ri * 8 + iy][col * 8 + ix]:
                            mismatch += 1
        if mismatch:
            print("  FAIL  %d of %d live VRAM pixels in the floor band differ "
                  "from the art perspective_floor_gen renders"
                  % (mismatch, checked))
            ok = False
        else:
            print("  PASS  live VRAM carries the generated fan exactly: %d "
                  "pixels over %d distinct tiles" % (checked, len(cache)))

        print("  NOT MEASURED: the on-screen seam geometry — see this file's "
              "header for the three approaches tried and why each would have "
              "produced a number with no referent.")
    finally:
        await client.close()
        inst.reap()
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    args = ap.parse_args()
    print("perspective_floor_witness: %s" % args.rom)
    try:
        ok = asyncio.run(run(args.rom, args.lst))
    except WitnessError as e:
        print("  NOT MEASURED: %s" % e)
        return 2
    print("  %s" % ("OK" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
