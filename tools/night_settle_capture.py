#!/usr/bin/env python3
"""night_settle_capture — capture the NIGHT region's FADE edge and run until the cross-fade
has ACTUALLY settled, naming every frame from the state it was taken in.

WHY THIS EXISTS. `docs/captures/2026-09-13-regions-p2-night/t5-f272-settled.png` became the
evidence base for a colour ruling the owner is being asked to make, and it is not settled:
45.9% of its pixels decode to colours in neither the day nor the night palette
(docs/superpowers/notes/2026-09-16-night-palette-mechanism.md). The refutation was already in
that set's own README table, one column over -- the same row records `Pal_Fade_Frames` = 11,
a field `engine/ram.emp` spells "cross-fade frames remaining (0 = stable)". A human wrote the
word into the name because the CRAM *tracer* entry had reached its night value, and nothing
compared the name against the state tabulated beside it.

THE ANSWER IS NOT A CHECKER. A checker is a thing somebody has to remember to run, on the
right files, before believing a name. Here the name is DERIVED from the state at the moment
of capture, so it cannot disagree with it. `tools/capture_settle.py` is that derivation; this
tool is the only thing that feeds it live reads. Every emitted filename is:

    <leg>-k<+NNN>-t<NNNNN>-cx<NNNN>-r<NN>-pf<NN>-<state>.png
      k     ticks from the crossing tick (k = 0 is the first tick the night region is current)
      t     Logic_Tick
      cx    the CAMERA CENTRE x -- the point Region_Resolve tests
      r     the region row the ROM's own table puts that centre in
      pf    Pal_Fade_Frames as read on that tick
      state `settled`, or the FIRST settle clause that refused (`fading`, `armed`, `layer`,
            `buf`, `cram`, `lag`, `hold`), or `unknown` if a clause could not be evaluated

`settled` reaches a filename only from `capture_settle.assess()` returning it over a live
read. Run the 2026-09-13 numbers for frame 272 through it and you get
`in-k+005-t00272-cx3488-r09-pf11-fading.png`; there is no argument to this tool that produces
the other name. tools/test_capture_settle.py holds that offline, against that README's own
parsed table.

WHAT "SETTLED" MEANS HERE, and it is seven clauses rather than one. `Pal_Fade_Frames == 0`
is NECESSARY and NOT SUFFICIENT -- it is one of four layers `Palette_Compose` runs over lines
1-3, a 0 can mean CANCELLED as well as ARRIVED (`Palette_LoadPal`'s snap arm clears it), the
buffer is not CRAM (the DMA is in the next VBlank) and CRAM is not the picture (the paused
screenshot is the previously completed video frame). capture_settle.py's header derives all
of it, including N = 3, the number of consecutive identical-CRAM samples required, which
comes from the compose->CRAM->frame pipeline depth and not from taste.

THE ROUTE. Cold boot, hold RIGHT in DEBUG free-flight (PLAYER_DEBUG_FLY_SPEED px/tick, the
camera's own step cap), through the authored night edge at `OJZ_NIGHT_X0` on act 1's region
row for `OJZ_Preset_Night` (`transition: 1`, so the palette CROSS-FADES rather than snaps --
that is the edge this tool is for; x = 5600's `OJZ_Preset_NightSnap` is the other one and
`tools/e2_snap_capture.py` owns it). The hold is never released: a stationary variant was
considered and left out rather than shipped untested, and the fade settles well inside the
region at flight speed.

WHY NOT A MODE OF e2_snap_capture.py. Its Rig, its readers, its region table and now its
naming policy ARE shared -- the two tools import the same four modules, which is where the
"two answers to one question" risk actually lives. What is NOT shared is the loop, and it
cannot be: e2 captures a fixed window (`PRE`/`POST = 16`) around a crossing, which is the
right shape for an instantaneous event and the WRONG shape here. A fade's length is not
known in advance (`Palette_DoFade` steps only on ODD decremented counts and closes early on
arrival, so it ends at 2*max(d) - 1 composes for a distance d this tool MEASURES rather than
assumes), and the settle window extends past it. A `--stop settle` mode would have put two
loops and two naming policies in one file to avoid two files -- the same defect wearing the
other hat. See docs/DEFERRED_WORK.md for the note.

⚠ WHAT THIS STILL CANNOT SETTLE. These are stills. Whether the fade READS as a transition is
a motion percept and a contact sheet cannot produce it. And the ruling's channel means should
be re-measured off the frames named `settled` here, never off the old set.

RUN IT FROM THE AEON ROOT. Every default path (`--rom`, `--lst`, `--outdir`) is relative to
the working directory, so `cd /path/to/aeon && python3 tools/night_settle_capture.py` is the
form. Run `--check` FIRST: it starts no emulator, costs about a second, and covers the whole
ROM-side failure surface, so a foreground Oracle run is never spent on a ROM that would have
been refused.

Exit 0  the run settled and the frames are written
     2  COULD NOT RUN (a premise refused, a symbol is missing, the route has moved) or the
        fade did not settle within the ceiling. The report and frames are still written when
        the ceiling is what stopped it -- an unsettled run is a finding, not an absence -- and
        NOTHING in it is named `settled`. It asserts nothing else.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

AEON = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import capture_settle as cs               # noqa: E402  the predicate and the namer
import region_fade_witness as rfw         # noqa: E402  the Rig, the walk, the readers
import region_table                       # noqa: E402
from aether import BusClient              # noqa: E402
from aether_instance import aether_emulator  # noqa: E402

PRE = 4      # ticks captured BEFORE the crossing tick (the day-palette control)
LEAD = 10    # ticks of approach before the capture window opens

#: Symbols this tool reads that region_fade_witness does not. Named here so a missing one is
#: a refusal that says which, not a KeyError in the middle of a walk.
EXTRA_SYMBOLS = ("Pal_Op", "Pal_Base_Dirty", "Pal_Cycle_Script")


def ceiling_ticks(fade_frames: int, stable: int, settled_frames: int) -> int:
    """How many ticks past the arm the capture may run before the run is a FINDING.

    Derived, not picked. `Palette_DoFade` decrements once per compose and one compose is one
    logic tick, so the fade itself cannot exceed `PAL_FADE_FRAMES` ticks even on its backstop
    path; `stable` more are needed for the window and `settled_frames` for the tail. It is
    DOUBLED because a lag frame costs video frames rather than logic ticks and the doubling
    is the only slack this number has -- anything past it is not a longer wait, it is a fade
    that did not end, and the tool says so instead of waiting."""
    return 2 * (fade_frames + stable + settled_frames)


async def rd(b, sym, name, width):
    return await rfw.rd(b, sym[name], width)


async def sample_row(rig, b, sym, i: int) -> dict:
    """One tick's full state: region_fade_witness's sample plus the three fields the `layer`
    clause needs, keyed the way capture_settle.assess() reads them."""
    s = await rig.sample(f"n{i}", cram=True)
    return {
        "i": i, "tick": s["tick"], "frame": s["frame"], "lag": s["lag"], "dtick": s["dtick"],
        "centre_x": s["centre"][0], "centre_y": s["centre"][1],
        "region": s["region"], "row": s["row"],
        "fade_frames": s["frames"], "fade_request": s["request"],
        "pal_active": s["active"],
        "pal_op": await rd(b, sym, "Pal_Op", 1),
        "pal_base_dirty": await rd(b, sym, "Pal_Base_Dirty", 1),
        "pal_cycle_script": await rd(b, sym, "Pal_Cycle_Script", 4),  # RECORDED, not a clause
        "buffer": s["pal"], "target": s["target"], "cram": s["cram"],
    }


def public(r: dict) -> dict:
    """The report's per-tick record: the 48-word arrays as hex, everything else verbatim."""
    out = {k: v for k, v in r.items()
           if k not in ("buffer", "target", "cram", "raw_png")}
    for k in ("buffer", "target", "cram"):
        out[k] = [f"{w:04X}" for w in r[k]]
    out["region"] = hex(r["region"])
    out["pal_cycle_script"] = hex(r["pal_cycle_script"])
    return out


def enrich(kept: list[dict], verdicts: dict, k0: int) -> tuple[list[dict], list[dict]]:
    """Attach `k` and the verdict to every captured sample, DERIVE its filename, and split
    off the approach tail that gets deleted.

    Pure, so tools/test_night_settle_capture.py drives the shipped naming path over a
    simulated run rather than over a re-implementation of it. `frame_name` is the only
    producer of the name, and it refuses a `settled` word the verdict did not earn."""
    keep, dropped = [], []
    for r in kept:
        r["k"] = r["i"] - k0
        (keep if r["k"] >= -PRE else dropped).append(r)
    for r in keep:
        v = verdicts[r["i"]]
        r["raw_png"] = r["png"]
        r["png"] = cs.frame_name("in", r, v)
        r["settle_state"] = v.word
        r["settled"] = v.settled
        r["settle_decided"] = v.decided
        r["settle_reasons"] = list(v.reasons)
        r["cram_stable_run"] = v.stable_run
        # Which frames got the full 48-word Palette_Buffer-vs-Pal_Target comparison. A
        # certified frame with this False is certified on strictly weaker evidence (the
        # layer gates + CRAM stability), because Pal_Target was not authoritative there.
        r["target_checked"] = v.target_checked
        r["target_note"] = v.target_note
    return keep, dropped


def build_report(args_rom: str, args_lst: str, rom_md5: str, edge: int, fade: dict,
                 left_index: int, fly: int, facts, cap: int, series: list[dict], k0: int,
                 keep: list[dict], model: dict | None, stopped: str | None) -> dict:
    """The report.json body. Pure: the offline test builds one from a simulated run."""
    # SCOPED TO THE SUBJECT. A frame before the crossing can be perfectly settled -- on the
    # DAY palette -- and it is, which is the control that proves the predicate is not
    # vacuously false. But offering one as "a settled frame" in a set about the night look
    # would be the 2026-09-13 mistake with the sign flipped: a correctly named frame used as
    # evidence for something it is not evidence for. The two lists are kept apart.
    settled_frames = [r for r in keep if r["settled"] and r["row"] == fade["index"]]
    control_frames = [r for r in keep if r["settled"] and r["row"] != fade["index"]]
    return {
        "tool": "tools/night_settle_capture.py",
        "rom": args_rom, "lst": args_lst, "rom_md5": rom_md5,
        "edge_x": edge, "fade_row": fade["index"],
        "fade_row_extent": [fade["x0"], fade["x1"], fade["y0"], fade["y1"]],
        "left_row": left_index,
        "fly_px_per_tick": fly,
        "settle": {
            "stable_ticks_required": facts.stable_ticks,
            "compose_to_cram_ticks": cs.COMPOSE_TO_CRAM_TICKS,
            "cram_to_captured_frame_ticks": cs.CRAM_TO_CAPTURED_FRAME_TICKS,
            "channel_mask": f"{facts.chan_mask:04X}",
            "pal_fade_frames_const": facts.fade_frames_const,
            "ceiling_ticks_past_the_arm": cap,
            "derivation": [{"claim": c, "from": w} for c, w in facts.citations],
        },
        "crossing_tick": series[k0]["tick"],
        "crossing_centre_x": series[k0]["centre_x"],
        "model_cross_check": model,
        "settled": stopped is None,
        "stopped_because": stopped,
        "settled_frames": [r["png"] for r in settled_frames],
        "control_frames": [r["png"] for r in control_frames],
        # THE CONTROL IS A RESULT, NOT A BY-PRODUCT (live run 2026-09-16). The first real
        # run produced ZERO controls because the `buf` clause falsely refused every
        # pre-fade frame, the summary said "0 day-palette controls" in passing, and nobody
        # read it. A control count of zero means the predicate was never shown to be
        # capable of saying `settled` anywhere but on the subject, so this run is not
        # evidence that it can. It is a named top-level field, a loud stderr block and a
        # README banner -- three places, because one was demonstrably passed over.
        "control_empty": not control_frames,
        "settled_frames_with_target_compared":
            [r["png"] for r in settled_frames if r.get("target_checked")],
        "ticks": [public(r) for r in keep],
    }


def premise(rom_path: str, lst_path: str) -> dict:
    """Everything this capture needs to be true BEFORE an emulator is started, checked with
    no emulator: the engine derivation, the symbols, and the act table's own geometry.

    Pure and offline, which is what `--check` runs and what lets a non-emulator session (and
    the offline test suite) exercise every refusal below against a real ROM + listing pair.
    Every refusal NAMES the thing that moved: an empty run that looks like a finding is the
    exact failure mode this parcel exists to remove."""
    facts = cs.derive_engine_facts(AEON)
    fly = rfw.src_const("games/sonic4/player/player_common.emp", "PLAYER_DEBUG_FLY_SPEED")
    half_w = rfw.src_const("engine/system/constants.emp", "CAM_SCREEN_HALF_W")
    half_h = rfw.src_const("engine/system/constants.emp", "CAM_SCREEN_HALF_H")
    edge = rfw.src_const("games/sonic4/data/levels/ojz/act1/act_descriptor.emp", "OJZ_NIGHT_X0")
    ep = rfw.preset_offsets()

    sym = rfw.parse_lst(lst_path)
    for need in ("GameState_OJZScroll_Init", "GameState_OJZScroll_Update", "Camera_X",
                 "Camera_Y", "Region_Current", "Pal_Fade_Frames", "Pal_Fade_Request",
                 "Pal_Active", "Pal_Target", "Palette_Buffer", "Logic_Tick", "Frame_Counter",
                 "Lag_Frame_Count", "OJZ_Act1_Descriptor") + EXTRA_SYMBOLS:
        if need not in sym:
            raise rfw.SetupError(f"symbol {need} is not in {lst_path} — this tool needs the "
                                 "sonic4 DEBUG listing")

    rom = Path(rom_path).read_bytes()
    try:
        rows = region_table.read_regions(rom, sym["OJZ_Act1_Descriptor"])
    except region_table.LayoutError as e:
        raise rfw.SetupError(str(e)) from e

    def u16(a): return int.from_bytes(rom[a:a + 2], "big")
    def u32(a): return int.from_bytes(rom[a:a + 4], "big")
    for r in rows:
        pr = r["effects"]
        r["transition"] = u16(pr + ep["ep_transition"])
        r["pal_ptr"] = u32(pr + ep["ep_pal"])
        r["raster_ptr"] = u32(pr + ep["ep_raster"])
        r["pal"] = [u16(r["pal_ptr"] + 2 * n) for n in range(48)]

    y_c = 256                                   # the DEBUG spawn's flight line
    fade = next((r for r in rows if r["x0"] == edge and r["y0"] <= y_c <= r["y1"]), None)
    if fade is None:
        raise rfw.SetupError(
            f"no region row in {rom_path} starts at x = {edge} (OJZ_NIGHT_X0) on the spawn's "
            f"flight line y = {y_c}. The night region has moved or left the act table "
            "(games/sonic4/data/levels/ojz/act1/act_descriptor.emp).")
    if fade["transition"] == 0:
        raise rfw.SetupError(
            f"the region at x = {edge} binds a preset with ep_transition = 0, so its palette "
            "SNAPS and there is no fade to settle. This tool captures the FADE edge; "
            "tools/e2_snap_capture.py captures the snap one.")
    left = region_table.region_at(rows, edge - 1, y_c)
    if left is None or left["pal"] == fade["pal"]:
        raise rfw.SetupError(
            f"the region left of x = {edge} "
            f"{'does not exist' if left is None else 'binds the SAME ep_pal'}, so nothing "
            "changes colour at this edge and there is no fade to watch settle.")
    none_prog = sym.get("Raster_Program_None")
    if none_prog is None:
        raise rfw.SetupError("symbol Raster_Program_None is not in the listing — the "
                             "mid-frame-CRAM premise below cannot be checked")
    if fade["raster_ptr"] != none_prog:
        raise rfw.SetupError(
            f"the night region binds raster program {fade['raster_ptr']:#x}, not "
            f"Raster_Program_None ({none_prog:#x}). A raster program can write CRAM DURING "
            "the scan, so a single CRAM read is a mixture of two palettes and can be "
            "perfectly stable frame to frame while the picture is not the palette. The "
            "settle predicate cannot see that, so this tool refuses rather than name frames "
            "it cannot vouch for. (capture_settle.py's header, last section.)")

    d = rfw.channel_distance(left["pal"], fade["pal"])
    return {"facts": facts, "fly": fly, "half_w": half_w, "half_h": half_h, "edge": edge,
            "sym": sym, "rom": rom, "rows": rows, "fade": fade, "left": left,
            "distance_from_the_left_regions_palette": d,
            "k_arrival_predicted": (2 * d - 1) if d else 0,
            "ceiling": None}


async def run(args, sock) -> int:
    pre = premise(args.rom, args.lst)
    facts, fly, half_w, half_h = pre["facts"], pre["fly"], pre["half_w"], pre["half_h"]
    edge, sym, rom, rows = pre["edge"], pre["sym"], pre["rom"], pre["rows"]
    fade, left = pre["fade"], pre["left"]

    out = Path(args.outdir)
    # A RE-RUN MUST SUPERSEDE, NOT BLEND. This tool overwrites README.md and report.json but
    # its PNGs are named from state, so a second run into the same directory leaves the first
    # run's frames sitting beside the second's under a README that describes only the second.
    # That is how a capture set stops being evidence. Refuse, and say where to put it.
    if (out / "report.json").exists() and not args.force:
        raise rfw.SetupError(
            f"{out} already holds a report.json from an earlier run. This tool would rewrite "
            "the README and the report but NOT remove that run's frames, which are named "
            "from their own state — you would get two runs' PNGs under one README describing "
            "one of them. Point --outdir at a new directory (the old set stays as the record "
            "of what it recorded), or pass --force if you genuinely mean to overwrite in "
            "place.")
    out.mkdir(parents=True, exist_ok=True)

    b = BusClient(socket_path=sock, client_id="nightsettle", client_name="night_settle_capture")
    await b.connect()
    for m in ("emulator/step", "emulator/run_to", "emulator/hold", "emulator/release_all",
              "emulator/read_cram", "emulator/screenshot"):
        if not b.supports(m):
            raise rfw.SetupError(f"the server does not advertise `{m}`")
    await rfw._c(b, "emulator/load_symbols", {"path": args.lst})
    rig = rfw.Rig(b, sym, rows, half_w, half_h)
    await rig.boot()
    for _ in range(3):
        await rig.tick()

    cap = ceiling_ticks(facts.fade_frames_const, facts.stable_ticks, args.settled_frames)
    print(f"night_settle_capture: edge x={edge}, row {fade['index']}, fly {fly} px/tick, "
          f"N={facts.stable_ticks} stable samples required, ceiling {cap} ticks past the arm",
          file=sys.stderr)

    await rig.hold("right")
    series: list[dict] = []          # every sample, for the stability window
    kept: list[dict] = []            # the samples that got a screenshot
    verdicts: dict = {}
    k0 = None                        # the crossing tick's index into `series`
    settled_run = 0
    stopped = None
    start_pal = None

    for i in range(rfw.WALK_MAX_TICKS):
        await rig.tick()
        r = await sample_row(rig, b, sym, i)
        series.append(r)
        near = abs(r["centre_x"] - edge) <= (PRE + LEAD) * fly
        if near or k0 is not None:
            shot = out / f"raw-i{i:04d}.png"
            await rfw._c(b, "emulator/screenshot", {"path": str(shot)})
            r["png"] = shot.name
            kept.append(r)
            v = cs.assess(series, facts)
            verdicts[i] = v
        if k0 is None and r["row"] == fade["index"]:
            k0 = i
            start_pal = series[i - 1]["buffer"] if i else None
        if k0 is not None:
            if r["row"] != fade["index"]:
                stopped = (f"the camera left the night region at tick {r['tick']} "
                           f"(centre x={r['centre_x']}, row {r['row']}) before the fade "
                           "settled — the route is too short for this fade")
                break
            v = verdicts[i]
            settled_run = settled_run + 1 if v.settled else 0
            if settled_run >= args.settled_frames:
                break
            if i - k0 >= cap:
                stopped = (f"the fade had not settled {cap} ticks after the arm (the "
                           f"ceiling; PAL_FADE_FRAMES = {facts.fade_frames_const}). The last "
                           f"verdict was `{v.word}`: " + "; ".join(v.reasons))
                break
    await rig.hold(None)

    if k0 is None:
        raise rfw.SetupError(
            f"held RIGHT for {rfw.WALK_MAX_TICKS} ticks and the camera centre never entered "
            f"region row {fade['index']} (x {edge}..{fade['x1']}) — the route has moved")

    # ---- name every kept frame from its own verdict, and drop the approach tail ----------
    keep, dropped = enrich(kept, verdicts, k0)
    for r in dropped:
        (out / r["png"]).unlink(missing_ok=True)
    for r in keep:
        (out / r.pop("raw_png")).replace(out / r["png"])

    # ---- the model, as a CROSS-CHECK printed beside the reads and never as a source ------
    # The 2026-09-13 README asserted "settled at k = 5, the derived 2d-1 for d = 3" and the
    # counter beside it said 11. A model that disagrees with the reads is reported, loudly,
    # and the NAMES still come from the reads.
    model = None
    if start_pal is not None:
        d = rfw.channel_distance(start_pal, fade["pal"])
        arm = series[k0]
        # k counts COMPOSES since the arm; the arming tick's own compose is k = 1, which is
        # series[k0]. (region_fade_witness.fade_model uses the same origin.)
        first_eq = next((r["i"] - k0 + 1 for r in series[k0:]
                         if all(((x ^ y) & facts.chan_mask) == 0
                                for x, y in zip(r["buffer"], fade["pal"]))), None)
        model = {
            "max_channel_distance_from_the_live_buffer": d,
            "k_arrival_predicted_2d_minus_1": (2 * d - 1) if d else 0,
            "k_arrival_measured": first_eq,
            "fade_frames_on_the_arming_tick": arm["fade_frames"],
            "agrees": first_eq == ((2 * d - 1) if d else 0),
        }

    report = build_report(args.rom, args.lst, hashlib.md5(rom).hexdigest(), edge, fade,
                          left["index"], fly, facts, cap, series, k0, keep, model, stopped)
    settled_frames = report["settled_frames"]
    (out / "report.json").write_text(json.dumps(report, indent=2))
    (out / "README.md").write_text(readme(report))

    for r in keep:
        print(f"  k={r['k']:+4d} t={r['tick']:5d} cx={r['centre_x']:5d} row={r['row']} "
              f"pf={r['fade_frames']:2d} -> {r['settle_state']}", file=sys.stderr)
    print(f"{len(keep)} frames in {out}; {len(settled_frames)} inside the night region "
          f"named `{cs.SETTLED_WORD}`, of which "
          f"{len(report['settled_frames_with_target_compared'])} also passed the 48-word "
          "Palette_Buffer-vs-Pal_Target comparison", file=sys.stderr)
    if report["control_empty"]:
        print("", file=sys.stderr)
        print("=" * 78, file=sys.stderr)
        print("CONTROL EMPTY — this run certified 0 frames outside the night region.",
              file=sys.stderr)
        print("  The approach frames before the crossing are the BASELINE the night colour",
              file=sys.stderr)
        print("  is judged against, AND the control that the predicate can say "
              f"`{cs.SETTLED_WORD}` at all", file=sys.stderr)
        print("  somewhere other than on its subject. Zero of them means this run is NOT",
              file=sys.stderr)
        print("  evidence that the predicate can certify anything: a predicate that only",
              file=sys.stderr)
        print("  ever certifies the thing you are looking for has not been shown to refuse",
              file=sys.stderr)
        print("  for a reason. Read the `settle_reasons` of the k < 0 rows in report.json",
              file=sys.stderr)
        print("  BEFORE using the night frames. This exact state shipped once, on "
              "2026-09-16,", file=sys.stderr)
        print("  as one line reading `0 day-palette controls` that two people passed over.",
              file=sys.stderr)
        print("=" * 78, file=sys.stderr)
    else:
        print(f"  control: {len(report['control_frames'])} frame(s) outside the night region "
              f"also certified — the predicate is not vacuously false on this run",
              file=sys.stderr)
    if stopped is not None:
        print(f"night_settle_capture: DID NOT SETTLE — {stopped}", file=sys.stderr)
        print("The frames and report ARE written, and none of them is named "
              f"`{cs.SETTLED_WORD}`. That is a finding about the fade, not a capture "
              "failure; do not treat this exit as an absence of evidence.", file=sys.stderr)
        return 2
    if model is not None and not model["agrees"]:
        print(f"night_settle_capture: the step model and the reads DISAGREE — a channel "
              f"distance of {model['max_channel_distance_from_the_live_buffer']} predicts "
              f"arrival at k = {model['k_arrival_predicted_2d_minus_1']} and the buffer "
              f"first equalled the target at k = {model['k_arrival_measured']}. The NAMES "
              "come from the reads; see report.json `model_cross_check`.", file=sys.stderr)
    return 0


def readme(rep: dict) -> str:
    s = rep["settle"]
    lines = [
        f"# The night region's FADE edge at x = {rep['edge_x']}, captured until it settled",
        "",
        f"`{rep['rom']}` md5 `{rep['rom_md5'][:8]}`, symbols `{rep['lst']}`. Cold boot, one "
        f"held RIGHT in DEBUG free flight ({rep['fly_px_per_tick']} px/tick). \"Centre\" is "
        "`Camera_X` + `CAM_SCREEN_HALF_W`, the point `Region_Resolve` tests. The night "
        f"region is row {rep['fade_row']}, x {rep['fade_row_extent'][0]}.."
        f"{rep['fade_row_extent'][1]}.",
        "",
        "**Every filename here was derived from the state read on that tick, by "
        "`tools/capture_settle.py`. A frame is called "
        f"`{cs.SETTLED_WORD}` only where that predicate said so from a live read; otherwise "
        "the name carries the first clause that refused.** This set exists because "
        "`docs/captures/2026-09-13-regions-p2-night/t5-f272-settled.png` was named by hand "
        "and is mid-fade.",
        "",
        "## What `settled` was required to mean",
        "",
        f"Seven clauses, all of them, from a live read, with CRAM lines 1-3 identical across "
        f"**{s['stable_ticks_required']}** consecutive samples:",
        "",
        "| clause | what it reads |",
        "|---|---|",
        "| `fading` | `Pal_Fade_Frames == 0` |",
        "| `armed` | `Pal_Fade_Request == 0` |",
        "| `layer` | `Pal_Base_Dirty`, `PAL_ACT_CYCLE`, `Pal_Op` — the three gates "
        "`Palette_Compose` branches on for the layers that move lines 1-3 |",
        f"| `buf` | all 48 words of `Palette_Buffer` lines 1-3 == `Pal_Target` under "
        f"`${s['channel_mask']}` — ARRIVED, not merely stopped |",
        "| `cram` | CRAM lines 1-3 == the buffer (the DMA runs in the next VBlank) |",
        "| `lag` | the window took no lag frame |",
        f"| `hold` | CRAM identical across {s['stable_ticks_required']} samples |",
        "",
        f"N = {s['stable_ticks_required']} is derived: "
        f"{s['compose_to_cram_ticks']} tick compose -> CRAM + "
        f"{s['cram_to_captured_frame_ticks']} tick CRAM -> the completed video frame a "
        "paused screenshot returns + 1, because N samples span N-1 intervals. Full "
        "derivation and its citations are in `report.json` under `settle.derivation`.",
        "",
        "## The run",
        "",
        f"Crossing at Logic_Tick {rep['crossing_tick']}, camera centre x "
        f"{rep['crossing_centre_x']}. `k` counts ticks from there.",
        "",
        "`target?` is whether the 48-word `Palette_Buffer` vs `Pal_Target` comparison "
        "actually ran on that tick. It can only run where `Pal_Target` is authoritative — a "
        "fade has been seen in flight and no snap install since — because "
        "`Palette_LoadPal`'s fade arm is its only writer and its snap arm never updates it. "
        "A `settled` row with `target? no` is certified on the layer gates and CRAM "
        "stability alone: strictly weaker evidence, a real certification, and not the same "
        "one.",
        "",
        "| k | tick | centre x | row | `Pal_Fade_Frames` | CRAM stable run | target? | state "
        "| file |",
        "|---:|---:|---:|---:|---:|---:|:-:|---|---|",
    ]
    for r in rep["ticks"]:
        lines.append(f"| {r['k']:+d} | {r['tick']} | {r['centre_x']} | {r['row']} | "
                     f"{r['fade_frames']} | {r['cram_stable_run']} | "
                     f"{'yes' if r.get('target_checked') else 'no'} | "
                     f"`{r['settle_state']}` | `{r['png']}` |")
    lines += [""]
    if rep["settled"]:
        lines += [f"**{len(rep['settled_frames'])} frame(s) INSIDE THE NIGHT REGION are "
                  f"named `{cs.SETTLED_WORD}`** and they are the only ones any night colour "
                  "measurement may be taken from: " +
                  ", ".join(f"`{n}`" for n in rep["settled_frames"]) + ". "
                  f"{len(rep['settled_frames_with_target_compared'])} of them also passed "
                  "the 48-word `Pal_Target` comparison.", ""]
        if rep["control_empty"]:
            lines += ["⚠ **CONTROL EMPTY — read this before using the frames above.** This "
                      "run certified **zero** frames outside the night region. The approach "
                      "frames are both the day-palette BASELINE the night colour is judged "
                      "against and the control that the predicate can say "
                      f"`{cs.SETTLED_WORD}` somewhere other than on its own subject. With "
                      "none, this run is not evidence that the predicate can certify "
                      "anything: read the `settle_reasons` of the `k < 0` rows in "
                      "`report.json` and find out why they were refused before trusting the "
                      "night frames.", ""]
        else:
            lines += [f"The {len(rep['control_frames'])} approach frame(s) before the "
                      f"crossing are also named `{cs.SETTLED_WORD}` — correctly, on the DAY "
                      "palette. They are two things at once: the **baseline** any night "
                      "colour measurement should be compared against, and the **control** "
                      "that the predicate is not vacuously false. They are NOT night "
                      "evidence. The region row in each name (`r` field) tells them apart.",
                      ""]
    else:
        lines += ["⚠ **THE FADE DID NOT SETTLE INSIDE THIS RUN.** " +
                  str(rep["stopped_because"]) + f" **No frame inside the night region is "
                  f"named `{cs.SETTLED_WORD}`, and none of them may be used as a "
                  "settled-night reference.** (Approach frames before the crossing may still "
                  "be named settled — on the DAY palette; they are a control, not night "
                  "evidence.) This is a finding about the fade, not a missing capture.", ""]
    m = rep.get("model_cross_check")
    if m:
        lines += [
            "## The step model, as a cross-check and never as a source",
            "",
            "`Palette_DoFade` steps on ODD decremented counts and closes early on arrival, so "
            "a channel distance `d` from the LIVE buffer predicts arrival at `2d - 1` "
            "composes. Measured here from the buffer as it stood at the arm, not assumed:",
            "",
            f"* max channel distance `d` = **{m['max_channel_distance_from_the_live_buffer']}**",
            f"* predicted arrival k = **{m['k_arrival_predicted_2d_minus_1']}**",
            f"* measured arrival k = **{m['k_arrival_measured']}**",
            f"* `Pal_Fade_Frames` on the arming tick = **{m['fade_frames_on_the_arming_tick']}**",
            "",
            ("They agree." if m["agrees"] else
             "⚠ **They DISAGREE.** The names above come from the live reads regardless; the "
             "model is the thing to re-derive. The 2026-09-13 set asserted `k = 5, the "
             "derived 2d-1 for d = 3` in a row whose counter read 11, which is the same "
             "disagreement going unremarked."),
            "",
        ]
    lines += [
        "## What these stills cannot settle",
        "",
        "Whether the fade READS as a transition or as a fault is a motion percept at 60 Hz; "
        "a contact sheet cannot produce it for anyone. Use these to measure colour and to "
        "see which frame is which, and the running ROM to judge the look.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="night_settle_capture",
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default="s4.debug.bin",
                    help="the sonic4 DEBUG ROM to boot (default: %(default)s, RELATIVE to the "
                         "working directory — run this from the aeon root). The night region "
                         "is in both shapes, but the route needs DEBUG free flight.")
    ap.add_argument("--lst", default="s4.debug.lst",
                    help="the listing THAT ROM was built from (default: %(default)s). A "
                         "mismatched pair is the one thing this tool cannot detect.")
    ap.add_argument("--outdir", default="docs/captures/2026-09-16-night-settled",
                    help="where the frames, report.json and README.md go (default: "
                         "%(default)s, relative to the working directory). Created if "
                         "absent. The tool WRITES README.md and report.json there: point it "
                         "somewhere new rather than at an existing capture set.")
    ap.add_argument("--force", action="store_true",
                    help="write into an --outdir that already holds a report.json. Refused "
                         "by default: this tool's PNGs are named from state, so a second run "
                         "into the same directory leaves the first run's frames beside the "
                         "second's under a README describing only one of them. Prefer a new "
                         "--outdir, which supersedes the old set without destroying it.")
    ap.add_argument("--check", action="store_true",
                    help="run every premise this capture depends on and EXIT, without "
                         "starting an emulator: the engine derivation N is read from, the "
                         "symbols, the act's region table, and the four refusals (the night "
                         "row exists at OJZ_NIGHT_X0, it arms a fade, its neighbour binds a "
                         "different palette, it binds Raster_Program_None). Run this first "
                         "on any new ROM/listing pair — it costs no emulator and it is the "
                         "half of the failure surface a headless session can reach.")
    ap.add_argument("--settled-frames", type=int, default=3, metavar="N",
                    help="stop after N consecutive ticks whose verdict is `settled` "
                         "(default: %(default)s). More than one because a single settled "
                         "sample is a claim about one tick; three is a small run the owner "
                         "can compare against each other.")
    args = ap.parse_args()
    if args.settled_frames < 1:
        print("night_settle_capture: --settled-frames must be at least 1", file=sys.stderr)
        return 2
    if args.check:
        try:
            pre = premise(args.rom, args.lst)
        except (rfw.SetupError, cs.DerivationError) as e:
            print(f"night_settle_capture --check: WOULD NOT RUN — {e}", file=sys.stderr)
            return 2
        f, fade, left = pre["facts"], pre["fade"], pre["left"]
        cap = ceiling_ticks(f.fade_frames_const, f.stable_ticks, args.settled_frames)
        print(f"night_settle_capture --check: every premise holds for {args.rom} / {args.lst}")
        print(f"  night region      row {fade['index']}, x {fade['x0']}..{fade['x1']}, "
              f"y {fade['y0']}..{fade['y1']}, ep_transition {fade['transition']}")
        print(f"  left neighbour    row {left['index']}, x {left['x0']}..{left['x1']} "
              "(a DIFFERENT ep_pal, so a colour does move)")
        print(f"  raster program    Raster_Program_None — no mid-frame CRAM write to defeat "
              "the settle predicate")
        print(f"  channel distance  d = {pre['distance_from_the_left_regions_palette']} from "
              "the left region's ep_pal, so the step rule predicts the palette arrives at "
              f"compose k = {pre['k_arrival_predicted']}")
        print(f"                    (this is a PREDICTION from the AUTHORED palettes. The run "
              "measures d from the LIVE buffer at the arm and reports both; the NAMES never "
              "come from either.)")
        print(f"  settle window     N = {f.stable_ticks} consecutive identical-CRAM samples "
              f"(PAL_FADE_FRAMES = {f.fade_frames_const}, mask ${f.chan_mask:04X})")
        print(f"  ceiling           {cap} ticks past the arm = "
              f"{cap * pre['fly']} px at {pre['fly']} px/tick, against a "
              f"{fade['x1'] - fade['x0'] + 1} px region")
        print("  NOT CHECKED HERE, and only a live run can: that these symbols read the "
              "values they name, that the route still boots into free flight, and that the "
              "screenshot is the frame this tool's header says it is.")
        return 0
    try:
        # aether_emulator is a SYNC context manager spawned OUTSIDE asyncio.run — the proven
        # idiom for a headless one-shot capture (tools/e2_snap_capture.py, band_capture.py).
        with aether_emulator(args.rom, symbols=args.lst) as sock:
            return asyncio.run(run(args, sock))
    except (rfw.SetupError, cs.DerivationError) as e:
        print(f"night_settle_capture: COULD NOT RUN — {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
