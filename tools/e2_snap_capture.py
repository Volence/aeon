#!/usr/bin/env python3
"""e2_snap_capture — put the REGIONS-P2 E2 palette SNAP in front of the owner as PIXELS.

THE QUESTION E2 ASKS is a LOOK question, and this tool does NOT answer it. It produces the
frames the answer is given from: the frame before the crossing, the frame OF the crossing,
and the sixteen after it, on both approaches, with the engine state that says which frame is
which. The verdict is the owner's.

THE SUBJECT (docs/superpowers/notes/2026-09-15-regions-p2-e2.md). The sonic4 DEBUG ROM's act-1
region table carries a row the release table does not: x 5600..6143 across the top row, bound
to `OJZ_Preset_NightSnap` — row 2's own argument list with `OJZ_Palette_Night` in place of
`OJZ_Palette` and NOTHING else different (proved on the emitted bytes in the note). Its
`ep_transition` is 0, so `Effects_InstallPreset` skips `Palette_ArmFade` and the 48-entry
palette lands in ONE tick. The fade half of the same question already ships at x = 3400
(`OJZ_Preset_Night`, `transition: 1`), which is why this edge exists as well as that one
rather than instead of it: both are in the same ROM, on the same art, on one held RIGHT.

WHAT IT EMITS, per leg, into --outdir:
  <leg>-k<NN>.png     one frame per logic tick, k = -PRE .. +POST around the crossing tick
                      (k = 0 is the FIRST tick whose camera centre is inside the new region,
                      i.e. the first tick the new palette can be composed on)
  report.json         per-tick: centre x, the region row the ROM's own table puts it in,
                      Region_Current, Pal_Fade_Frames / _Request, and CRAM lines 1-3
  README.md           what to look at, written from the run's own numbers

THE LEGS. Both run at the camera's MAXIMUM speed, which is what a held direction in debug
free-flight gives (PLAYER_DEBUG_FLY_SPEED = 16 px/tick, matched to the camera's own step cap):
  in    day -> night, crossing x = 5600 rightwards
  out   night -> day, crossing back leftwards
WALKING SPEED IS NOT HERE, and that is a limit, not an oversight: leaving debug-fly drops the
player into physics, and where the ground is at x ~ 5500 in this act is not something this tool
can predict. The parcel note carries the hand recipe for the walked crossing.

⚠ WHAT A CAPTURE LIKE THIS CANNOT SETTLE. These are still frames. "Does it read as a glitch"
is a judgement about MOTION — a one-frame colour step surrounded by a scrolling scene, seen at
60 Hz — and a contact sheet of stills cannot produce that percept for anyone. Use this to see
exactly WHAT changes and on WHICH frame; use the ROM, in motion, to decide whether it reads.
The screenshot is taken with the emulator paused at GameState_OJZScroll_Update's entry, so
every frame in a leg is sampled at the same point in the frame and the series is comparable
tick to tick — but it is the PREVIOUS completed video frame, one tick behind the state
recorded beside it. The report's own `frame` column is the authority on that offset.

NAMING, AND THE ONE THING THIS TOOL MUST NEVER START DOING. `in-k+03.png` is derived from
a live read (k is the tick distance from the crossing the ROM's own table decided), and this
tool never claims a frame is SETTLED — a snap has nothing to settle. If that ever changes,
the stamp (`palette-settled`) may only come from `tools/capture_settle.py`, the one settle
predicate and name derivation. It exists because
`docs/captures/2026-09-13-regions-p2-night/t5-f272-settled.png` was named by hand from a CRAM
tracer entry and is mid-fade, with the refutation sitting in its own set's table one column
over. See that file's header and docs/DEFERRED_WORK.md for why these two tools share their
substrate and not their loop.

Exit 0 frames written · 2 could not run (setup error). It asserts NOTHING.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

AEON = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import region_fade_witness as rfw          # noqa: E402  the Rig, the walk, the readers
import region_table                        # noqa: E402
from aether import BusClient               # noqa: E402
from aether_instance import aether_emulator  # noqa: E402

PRE = 4            # ticks captured BEFORE the crossing tick
POST = 16          # ticks captured after it — the brief's "the frame of the crossing and 16"
LEAD = 10          # ticks of approach before the capture window opens
OVERSHOOT = 12     # ticks held past the edge before the return leg turns around


async def capture_leg(rig, b, sym, rows, out: Path, leg: str, button: str,
                      edge: int, want_row: int, fly: int) -> list[dict]:
    """Hold `button` until the camera centre's row becomes `want_row`, capturing a screenshot
    and a state row on every tick from PRE ticks before it to POST ticks after."""
    recs: list[dict] = []
    shots: list[tuple[int, str]] = []
    await rig.hold(button)
    k = None
    for i in range(rfw.WALK_MAX_TICKS):
        await rig.tick()
        s = await rig.sample(f"{leg}{i}", cram=True)
        close = abs(s["centre"][0] - edge) <= (PRE + LEAD) * fly
        if close or k is not None:
            shot = out / f"{leg}-i{i:03d}.png"
            await rfw._c(b, "emulator/screenshot", {"path": str(shot)})
            recs.append({"i": i, "tick": s["tick"], "frame": s["frame"],
                         "centre_x": s["centre"][0], "centre_y": s["centre"][1],
                         "row": s["row"], "region": s["region"],
                         "fade_frames": s["frames"], "fade_request": s["request"],
                         "cram_1_3": [f"{w:04X}" for w in s["cram"]],
                         "png": shot.name})
            shots.append((i, shot.name))
        if k is None and s["row"] == want_row:
            k = i
        if k is not None and i - k >= POST:
            break
    await rig.hold(None)
    if k is None:
        raise rfw.SetupError(f"leg `{leg}`: held {button} for {rfw.WALK_MAX_TICKS} ticks and the "
                             f"camera centre never entered row {want_row} — the route has moved")
    # relabel every captured tick by its distance from the crossing, and drop the approach tail
    for r in recs:
        r["k"] = r["i"] - k
    keep = [r for r in recs if -PRE <= r["k"] <= POST]
    for r in keep:
        src = out / r["png"]
        dst = out / f"{leg}-k{r['k']:+03d}.png"
        if src.exists():
            src.replace(dst)
        r["png"] = dst.name
    for r in recs:
        if r not in keep:
            (out / r["png"]).unlink(missing_ok=True)
    return keep


async def run(args, sock) -> int:
    fly = rfw.src_const("games/sonic4/player/player_common.emp", "PLAYER_DEBUG_FLY_SPEED")
    half_w = rfw.src_const("engine/system/constants.emp", "CAM_SCREEN_HALF_W")
    half_h = rfw.src_const("engine/system/constants.emp", "CAM_SCREEN_HALF_H")
    edge = rfw.src_const("games/sonic4/data/levels/ojz/act1/act_descriptor.emp", "OJZ_SNAP_X0")

    sym = rfw.parse_lst(args.lst)
    rom = Path(args.rom).read_bytes()
    rows = region_table.read_regions(rom, sym["OJZ_Act1_Descriptor"])

    # THE SUBJECT ROW, found by its geometry rather than by an index typed here: the row whose
    # left edge IS the snap edge. A ROM without one is a ROM this tool has nothing to capture in,
    # and that is a setup error with a name, never an empty run that looks like a finding.
    snap = next((r for r in rows if r["x0"] == edge and r["y0"] == 0), None)
    if snap is None:
        raise rfw.SetupError(
            f"no region row in {args.rom} starts at x = {edge} in the top row. This is the "
            "release table, or the E2 fixture is not in this ROM: it is DEBUG-shape only "
            "(games/sonic4/data/levels/ojz/act1/act_descriptor.emp, OJZ_E2_SNAP_ROWS).")
    left = next((r for r in rows if r["x1"] == edge - 1 and r["y0"] == 0), None)
    if left is None:
        raise rfw.SetupError(f"no region row ends at x = {edge - 1} in the top row")
    if rom[snap["effects"]:snap["effects"] + 4] == rom[left["effects"]:left["effects"] + 4]:
        raise rfw.SetupError(
            f"rows {left['index']} and {snap['index']} bind the SAME ep_pal, so nothing changes "
            "colour at this edge and there is no snap to look at")

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)

    b = BusClient(socket_path=sock, client_id="e2snap", client_name="e2_snap_capture")
    await b.connect()
    await rfw._c(b, "emulator/load_symbols", {"path": args.lst})
    rig = rfw.Rig(b, sym, rows, half_w, half_h)
    await rig.boot()
    for _ in range(3):
        await rig.tick()

    legs = {}
    legs["in"] = await capture_leg(rig, b, sym, rows, out, "in", "right",
                                   edge, snap["index"], fly)
    # carry on right, then come back through the edge for the night -> day approach
    await rig.hold("right")
    for _ in range(OVERSHOOT):
        await rig.tick()
    await rig.hold(None)
    legs["out"] = await capture_leg(rig, b, sym, rows, out, "out", "left",
                                    edge, left["index"], fly)

    report = {
        "rom": args.rom, "lst": args.lst, "edge_x": edge,
        "fly_px_per_tick": fly,
        "rows": {"left": left["index"], "snap": snap["index"]},
        "note": "k = 0 is the FIRST tick whose camera centre lies in the destination region; "
                "the palette install happens on that tick's Parallax_CheckBoundary and is "
                "composed by the same tick's Palette_Compose. The PNG beside a row is the "
                "previous completed video frame — see this tool's header.",
        "legs": legs,
    }
    (out / "report.json").write_text(json.dumps(report, indent=2))
    (out / "README.md").write_text(readme(report))
    for leg, recs in legs.items():
        zero = next(r for r in recs if r["k"] == 0)
        print(f"{leg}: {len(recs)} frames, crossing at centre x={zero['centre_x']} "
              f"(row {recs[0]['row']} -> {zero['row']}), Pal_Fade_Frames at k=0 is "
              f"{zero['fade_frames']}")
    print(f"frames and report in {out}")
    return 0


def readme(rep: dict) -> str:
    lines = [f"# REGIONS-P2 E2 — the palette SNAP at x = {rep['edge_x']}", "",
             f"ROM `{rep['rom']}`. Camera speed {rep['fly_px_per_tick']} px/tick (debug "
             "free-flight, the camera's own maximum).", "",
             "`k = 0` is the first tick the new region is current — the tick the palette is "
             "installed and composed. `k = -1` is the last tick of the old one.", ""]
    for leg, recs in rep["legs"].items():
        lines += [f"## leg `{leg}`", "",
                  "| k | centre x | row | Pal_Fade_Frames | frame |",
                  "|---|---|---|---|---|"]
        lines += [f"| {r['k']:+d} | {r['centre_x']} | {r['row']} | {r['fade_frames']} | "
                  f"`{r['png']}` |" for r in recs]
        lines += [""]
    lines += ["A `Pal_Fade_Frames` of 0 on every row is what makes this a SNAP: a cross-fade "
              "would count down from PAL_FADE_FRAMES over the rows after k = 0.", "",
              "These are stills. Whether the change READS as a transition or as a glitch is a "
              "judgement about motion; see the tool's header."]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--outdir", default="docs/captures/2026-09-15-regions-p2-e2")
    args = ap.parse_args()
    try:
        # aether_emulator is a SYNC context manager and is spawned OUTSIDE asyncio.run,
        # which is band_capture.py's proven idiom for a headless one-shot capture.
        with aether_emulator(args.rom) as sock:
            return asyncio.run(run(args, sock))
    except rfw.SetupError as e:
        print(f"e2_snap_capture: COULD NOT RUN — {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
