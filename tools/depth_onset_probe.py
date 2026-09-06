#!/usr/bin/env python3
"""depth_onset_probe -- does the SHIPPED section-4 showcase garble, and where is the onset?

THE SUBJECT. `Scene_Editor_ojz_act1_depth` (owner decision d-15) is bound to section 4 --
`EditorSceneBinding_OJZ_Act1_Sec4 = lower5(EditorScenes_OJZ_Act1[0])`, dispatched by
`ojz_act1_sec_scene(sec: 4)` -- and carries TWO curve layers:

    world_y 112   fb FACTOR_1_4   curve To(FACTOR_3_8)    |df| = 1/8
    world_y 160   fb FACTOR_1_2   curve To(FACTOR_1)      |df| = 1/2

`docs/witness/curve-desc-2026-09-06.md` established (a) the walker's ramp is arithmetically
exact in both directions, (b) the DIRECTION in CURVE-DESC's name is refuted, and (c) what
moves is a MAGNITUDE -- best-argued as the band's total Plane-B HScroll excursion against
`PLANE_W - SCREEN_W = 512 - 320 = 192 px`, which is where a plane column that leaves the
screen at x 320 re-enters at x 0 and appears twice in one band. That witness left TWO things
open, and this tool exists for both.

OPEN ITEM 1 -- THE SHIPPED SCENE WAS NEVER DRIVEN. Its onsets were computed
(`camX = 192/|df|` -> 1536 and 384) and booked as arithmetic, explicitly not a run.

OPEN ITEM 2 -- THE CONFOUND. Every arm of that witness held the band span at 224 lines, so
`excursion = rate x 224` and "excursion crosses 192 px" and "per-line rate crosses ~1
px/line" fit the data equally. THIS SCENE CLOSES IT WITH SHIPPED CONTENT, because its curve
bands are 48 and 64 lines tall instead of 224. Carrying the sec7 brackets across (clean at
excursion 176 / rate 0.79; garbled at excursion 353 / rate 1.58), the two models predict
DISJOINT onset windows on both bands:

    band 160 (span 64, |df| 1/2)   excursion model: camX 352..706    rate model: camX 101..202
    band 112 (span 48, |df| 1/8)   excursion model: camX 1408..2824  rate model: camX 302..605

So a single camera position inside a gap decides it. `camX 250` is the sharpest: band 160's
excursion is 125 px there -- under 192, so a plane column CANNOT appear twice, geometrically
-- while its per-line rate is 1.95 px/line, above the rate at which sec7 was already
garbled. Clean at camX 250 refutes the rate model; garbled refutes the excursion model.

TWO PHASES, AND ONLY THE FIRST ONE IS ABOUT THE GAME.

  --phase play    Warp through the mailbox to player positions inside section 4 and read
                  what the machine does. NOTHING is poked or pinned. This is the only
                  phase that answers "does the shipped showcase garble in play", and it is
                  also how the reachable camera range gets MEASURED rather than derived --
                  the grid is 3x3 at SECTION_SIZE $0800, but a section-to-camera-x mapping
                  is exactly the kind of thing that reads obvious and is wrong.

  --phase sweep   Hold the section-4 config and move the camera, including to positions
                  section 4 does not contain. OFF-PLAY BY CONSTRUCTION and labelled so
                  everywhere: it is a test of the MODEL, not of the game. The camera is
                  poked, then `Parallax_Current_Config` is re-pinned to the section-4
                  binding with `Parallax_Target_Config` and `Parallax_Transition_Frames`
                  zeroed, and all three are ASSERTED AGAIN at read time. That assertion is
                  not decoration: a staged TARGET config wins over Current inside
                  Parallax_Update's Step 1, so the pointer check alone reads green while
                  the walker builds from somebody else's config -- which is exactly what a
                  camera write across a section boundary produces (curve_probe's own
                  postmortem, and it cost that lane a wrong answer).

                  ⚠ THE PRESET IS NOT PINNED, ONLY THE PARALLAX CONFIG. A sample whose
                  camera sits outside section 4 carries a neighbouring section's preset --
                  palette, raster program, and this scene's two LIVE vsplit fires. The
                  reported `section` column is what discloses it, and a verdict that rests
                  on a picture from another section's preset says so.

EVIDENCE STANDARD, the same as the parcel before it: the Plane-B words are compared against
an expectation DERIVED from the scene's authored factors plus the live Camera_X (nothing is
read back off the band records the walker wrote), the pixels are REAL RASTER with
`source == "raster"` asserted, and every sample is written out as a PNG so the call can be
disagreed with.

    python3 tools/depth_onset_probe.py --rom s4.debug.bin --lst s4.debug.lst \\
        --scene games/sonic4/data/editor/effects/ojz_act1_depth.json \\
        --phase play --png-dir /tmp/depth
    python3 tools/depth_onset_probe.py --rom s4.debug.bin --lst s4.debug.lst \\
        --scene games/sonic4/data/editor/effects/ojz_act1_depth.json \\
        --phase sweep --camera-x 64,128,250,384,512,768,1024,1536,2048,2840,3840 \\
        --png-dir /tmp/depth --json /tmp/depth/sweep.json

Exit 0 = every sample measured. Exit 2 = UNMEASURABLE. Never a verdict on the picture: the
"garbled" call is a human look at the PNGs, and this tool prints the geometry that call has
to be consistent with.
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

AEON = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AEON / "tools"))
import curve_desc_probe as base                       # noqa: E402
from curve_desc_probe import Server, Setup, c, rd, rows, layers_from_scene  # noqa: E402
from raster_cost_probe import parse_lst               # noqa: E402
import curve_probe as cp                              # noqa: E402
import parallax_hscroll_probe as php                  # noqa: E402

LINES = base.LINES              # 224
SCREEN_W = 320
PLANE_W = 512                   # 64 cells x 8; VDP reg $10 = $11, boot_data.emp:186
WRAP_MARGIN = PLANE_W - SCREEN_W        # 192 -- DERIVED, not fitted
SECTION_SIZE = 0x0800           # engine/system/constants.emp:316
GRID_W = 3                      # games/sonic4/data/levels/ojz/act1/act_descriptor.emp:111

SETTLE = base.SETTLE            # 180
POST_WARP = base.POST_WARP      # 30
POST_POKE = 6                   # let a section crossing settle BEFORE pinning the config
POST_PIN = 4                    # ...and let the pinned config build a buffer
MAX_PARALLAX_BANDS = 16         # engine/system/constants.emp:746


def derive_with_drift(layers, cam_x, offs):
    """`curve_probe.derive_curve_buffer`, plus the BAND-DRIFT accumulator on each base.

    WHY THIS IS NOT "READING BACK WHAT THE WALKER WROTE", which is the property that makes
    the comparison mean anything. `Parallax_Update` builds a band's Plane-B word as
    `Decode_Factor_B(camX) + Parallax_Drift_Acc[band].pixels` (parallax.emp,
    `.cap_band_drift_accum`). The accumulator is a TIME-dependent state input that no
    amount of reading the scene document can predict -- exactly like `Camera_X`, which this
    tool has always read. What is still derived, and is the whole subject, is the RAMP: the
    far-end factor, the spread, the Bresenham pair and every line of the curve. `bc_step`,
    `bc_rem` and `bc_span` -- the walker's own output for that -- are never read.

    Measured 2026-09-06: the accumulator is EXACTLY ZERO for every band at every play
    position (120+ frames after the warp, and every shipped band record carries drift rate
    0), so in phase `play` this reduces to the plain derivation. It is non-zero only in
    phase `sweep`, where the camera poke and config re-pin seed it -- see the module
    docstring's note.

    ⚠ `Parallax_Drift_Acc` is indexed by CONFIG band index. Using it against `layers`
    positionally is only correct while Step 4a's rotation is the IDENTITY, which holds here
    because this scene's `v_offset` is 0. A rotated scene needs the rotation applied first.
    """
    tops = [t for (t, _a, _b, _c) in layers]
    ends = [tops[i + 1] if i + 1 < len(tops) else LINES for i in range(len(tops))]
    out = [None] * LINES
    for i, (top, fa, fb, to) in enumerate(layers):
        fg = cp.decode_factor(cam_x, fa)
        b0 = cp.decode_factor(cam_x, fb) + offs[i]
        span = ends[i] - top
        if span <= 0:
            continue
        if to is None:
            for y in range(top, ends[i]):
                out[y] = (php.u16(fg), php.u16(b0))
            continue
        end_word = cp.decode_factor(cam_x, to)
        whole, rem = cp.bresenham(php.s16(end_word - b0), span)
        acc, err = b0, 0
        for y in range(top, ends[i]):
            out[y] = (php.u16(fg), php.u16(acc))
            acc += whole
            err += rem
            if err >= span:
                err -= span
                acc += 1
    return out


NEEDED = ("EditorSceneBinding_OJZ_Act1_Sec4", "Warp_Req_X", "Warp_Req_Y",
          "Warp_Req_Flag", "Camera_X", "Camera_Y", "Hscroll_Buffer",
          "Parallax_Current_Vscroll_BG", "Parallax_Current_Config",
          "Parallax_Target_Config", "Parallax_Transition_Frames",
          "Parallax_Drift_Acc", "Debug_Scene_Freeze")


def require_symbols(sym, lst):
    """Every symbol this probe reads, checked up front so a missing one is a loud SETUP
    failure and never a silently skipped assertion. Returns the section-4 binding."""
    missing = [n for n in NEEDED if n not in sym]
    if missing:
        raise Setup(f"{lst}: symbols absent: {', '.join(missing)}")
    return sym["EditorSceneBinding_OJZ_Act1_Sec4"]


def band_spans(layers):
    """[(index, top, end, fa, fb, to)] for every layer, ends chained, last at 224."""
    out = []
    for i, (top, fa, fb, to) in enumerate(layers):
        end = layers[i + 1][0] if i + 1 < len(layers) else LINES
        out.append((i, top, end, fa, fb, to))
    return out


def analyse_band(bg, top, end):
    """Geometry of one band, computed from the MEASURED Plane-B words alone."""
    seg = bg[top:end]
    if len(seg) < 2:
        return None
    e = max(seg) - min(seg)
    steps = [seg[i] - seg[i - 1] for i in range(1, len(seg))]
    return {
        "top": top, "end": end, "lines": end - top,
        "excursion": e,
        "rate_max": max(steps, key=abs) if steps else 0,
        "rate_mean": round(e / (len(seg) - 1), 3),
        # THE DUPLICATION PREDICATE, and it is EXACT rather than empirical. A plane column
        # `col` shows at screen x = (col + h) mod 512. Over a band whose h spans E, the
        # union of visible plane-column windows is (320 + E) wide; once that exceeds the
        # plane's 512 it WRAPS, and some column is visible on two disjoint groups of rows
        # at two separated screen x. That is `E > 512 - 320 = 192`, from geometry only.
        "duplicates": e > WRAP_MARGIN,
        "excursion_over_margin": round(e / WRAP_MARGIN, 3),
    }


async def sample(b, sym, layers, png_dir, label, tag, pin_cfg=None):
    """One reading: assert the config, read the buffer, derive, capture, write a PNG."""
    checks = {}
    if pin_cfg is not None:
        cur = int.from_bytes(await rd(b, sym["Parallax_Current_Config"], 4), "big") & 0xFFFFFF
        tgt = int.from_bytes(await rd(b, sym["Parallax_Target_Config"], 4), "big") & 0xFFFFFF
        tfr = (await rd(b, sym["Parallax_Transition_Frames"], 1))[0]
        checks = {"current_config": hex(cur), "target_config": hex(tgt),
                  "transition_frames": tfr,
                  "config_ok": cur == pin_cfg, "target_ok": tgt == 0, "transition_ok": tfr == 0}
        if not (checks["config_ok"] and checks["target_ok"] and checks["transition_ok"]):
            raise Setup(
                f"{label}: the walker is not building from the section-4 config at read "
                f"time (current {hex(cur)} want {hex(pin_cfg)}, target {hex(tgt)} want 0x0, "
                f"transition {tfr} want 0). A staged TARGET wins over Current inside "
                f"Parallax_Update Step 1, so this sample would report another scene's ramp")

    cam_x = int.from_bytes(await rd(b, sym["Camera_X"], 4), "big") >> 16
    cam_y = int.from_bytes(await rd(b, sym["Camera_Y"], 4), "big") >> 16
    vs_bg = int.from_bytes(await rd(b, sym["Parallax_Current_Vscroll_BG"], 2), "big")
    raw = await rd(b, sym["Hscroll_Buffer"], LINES * 4)
    fg = [php.s16(int.from_bytes(raw[i * 4:i * 4 + 2], "big")) for i in range(LINES)]
    bg = [php.s16(int.from_bytes(raw[i * 4 + 2:i * 4 + 4], "big")) for i in range(LINES)]
    pix = await rows(b, 0, LINES)

    # The band-drift accumulator's PIXEL part, one signed word per config band -- a state
    # input, read for the same reason Camera_X is. See derive_with_drift's banner.
    dacc = await rd(b, sym["Parallax_Drift_Acc"], 4 * MAX_PARALLAX_BANDS)
    drift = [int.from_bytes(dacc[i * 4:i * 4 + 2], "big", signed=True)
             for i in range(len(layers))]

    exp = derive_with_drift(layers, cam_x, drift)
    exp_bg = [php.s16(exp[y][1]) for y in range(LINES)]
    exp_fg = [php.s16(exp[y][0]) for y in range(LINES)]
    d_bg = [bg[y] - exp_bg[y] for y in range(LINES)]
    d_fg = [fg[y] - exp_fg[y] for y in range(LINES)]
    # The same comparison with drift IGNORED, kept beside it: the difference between the
    # two columns is exactly what the accumulator is worth, and printing only the corrected
    # one would hide a state input behind a green number.
    exp0 = cp.derive_curve_buffer(layers, cam_x)
    n_nodrift = sum(1 for y in range(LINES)
                    if bg[y] != php.s16(exp0[y][1]))

    bands = []
    for (i, top, end, fa, fb, to) in band_spans(layers):
        a = analyse_band(bg, top, end)
        if a is None:
            continue
        a["layer"] = i
        a["is_curve"] = to is not None
        a["fb"] = "%03X" % fb
        a["to"] = None if to is None else "%03X" % to
        bands.append(a)

    png = None
    if png_dir:
        png = str(Path(png_dir) / f"depth-{tag}.png")
        try:
            from PIL import Image
            im = Image.new("RGB", (SCREEN_W, LINES))
            im.putdata([p for row in pix for p in row])
            im.save(png)
        except Exception as e:
            png = f"(not written: {e})"

    sec = (cam_y // SECTION_SIZE) * GRID_W + (cam_x // SECTION_SIZE)
    return {"label": label, "cam_x": cam_x, "cam_y": cam_y, "section": sec,
            "vscroll_bg": vs_bg, "checks": checks,
            "drift_px": drift, "n_bg_mismatch_no_drift": n_nodrift,
            "n_bg_mismatch": sum(1 for v in d_bg if v),
            "max_abs_bg_delta": max(abs(v) for v in d_bg),
            "max_abs_fg_delta": max(abs(v) for v in d_fg),
            "bands": bands, "bg": bg, "png": png, "pix": pix}


async def boot_into_section4(b, sym, lst, warp_x, warp_y):
    await c(b, "emulator/load_symbols", {"path": lst})
    await c(b, "emulator/reset", {})
    await c(b, "emulator/run_frames", {"frames": SETTLE})
    for a, v, w in ((sym["Warp_Req_X"], warp_x, 2), (sym["Warp_Req_Y"], warp_y, 2),
                    (sym["Warp_Req_Flag"], 1, 1)):
        await c(b, "emulator/write_memory", {"addr": hex(a), "value": v, "width": w})
    ack = None
    for i in range(1, 121):
        await c(b, "emulator/run_frames", {"frames": 1})
        if (await rd(b, sym["Warp_Req_Flag"], 1))[0] == 0:
            ack = i
            break
    if ack is None:
        raise Setup("Warp_Req_Flag never cleared in 120 frames -- not in the level state?")
    await c(b, "emulator/run_frames", {"frames": POST_WARP})
    return ack


async def run_play(rom, lst, scene, spots, png_dir):
    layers, sc, authored, vs, k = layers_from_scene(scene)
    sym = parse_lst(lst)
    want = require_symbols(sym, lst)
    out = []
    for (px, py) in spots:
        async with Server(rom, f"play{px}_{py}") as s:
            b = s.client
            ack = await boot_into_section4(b, sym, lst, px, py)
            cur = int.from_bytes(await rd(b, sym["Parallax_Current_Config"], 4),
                                 "big") & 0xFFFFFF
            r = await sample(b, sym, layers, png_dir, f"play x{px} y{py}",
                             f"play-{px}-{py}")
            r["ack"] = ack
            r["warp"] = (px, py)
            r["config_is_sec4"] = (cur == want)
            r["current_config"] = hex(cur)
            out.append(r)
    return out, layers


async def run_sweep(rom, lst, scene, cams, warp, png_dir):
    layers, sc, authored, vs, k = layers_from_scene(scene)
    sym = parse_lst(lst)
    want = require_symbols(sym, lst)
    out = []
    async with Server(rom, "sweep") as s:
        b = s.client
        await boot_into_section4(b, sym, lst, warp[0], warp[1])
        cur = int.from_bytes(await rd(b, sym["Parallax_Current_Config"], 4), "big") & 0xFFFFFF
        if cur != want:
            raise Setup(f"warping to {warp} did not install the section-4 scene "
                        f"(Parallax_Current_Config {hex(cur)}, want {hex(want)}) -- the "
                        f"sweep would hold the WRONG config")
        # FREEZE BEFORE ANY POKE. Camera_Update otherwise drags the camera back to the
        # player every frame and no poked position survives to the read.
        await c(b, "emulator/write_memory",
                {"addr": hex(sym["Debug_Scene_Freeze"]), "value": 1, "width": 1})
        await c(b, "emulator/run_frames", {"frames": 2})
        for cx in cams:
            # Camera_X is a 16.16 subpixel long: the pixel value goes in the HIGH word.
            await c(b, "emulator/write_memory",
                    {"addr": hex(sym["Camera_X"]), "value": (cx & 0xFFFF) << 16, "width": 4})
            await c(b, "emulator/run_frames", {"frames": POST_POKE})
            # Re-pin AFTER the crossing has settled, never before it.
            await c(b, "emulator/write_memory",
                    {"addr": hex(sym["Parallax_Transition_Frames"]), "value": 0, "width": 1})
            await c(b, "emulator/write_memory",
                    {"addr": hex(sym["Parallax_Target_Config"]), "value": 0, "width": 4})
            await c(b, "emulator/write_memory",
                    {"addr": hex(sym["Parallax_Current_Config"]), "value": want, "width": 4})
            await c(b, "emulator/run_frames", {"frames": POST_PIN})
            r = await sample(b, sym, layers, png_dir, f"sweep camX {cx}",
                             f"sweep-{cx:05d}", pin_cfg=want)
            if r["cam_x"] != cx:
                raise Setup(f"poked Camera_X {cx} but it reads {r['cam_x']} at the sample")
            out.append(r)
    return out, layers


def montage(samples, top, end, path, title):
    """One band's crop from every sample, stacked, each labelled with its camera x."""
    try:
        from PIL import Image, ImageDraw
    except Exception as e:
        return f"(not written: {e})"
    h = end - top
    pad, lab = 6, 12
    img = Image.new("RGB", (SCREEN_W + 2 * pad, lab + (h + lab + pad) * len(samples) + pad),
                    (20, 20, 24))
    d = ImageDraw.Draw(img)
    d.text((pad, 2), title, fill=(230, 230, 230))
    y = lab + pad
    for r in samples:
        sub = Image.new("RGB", (SCREEN_W, h))
        sub.putdata([p for row in r["pix"][top:end] for p in row])
        img.paste(sub, (pad, y))
        bd = next((x for x in r["bands"] if x["top"] == top), None)
        note = "camX %-5d E=%-5d rate=%-6s dup=%s" % (
            r["cam_x"], bd["excursion"], bd["rate_mean"], "YES" if bd["duplicates"] else "no")
        d.text((pad, y + h + 1), note, fill=(240, 240, 130))
        y += h + lab + pad
    img.save(path)
    return path


async def run_attrib(rom, lst, scene, spots, cols, rowspec):
    """WHICH PLANE OWNS THE PIXELS the curve bands cover, at each play position.

    THE QUESTION THIS ANSWERS, and it is not the same question as "does it garble". Two play
    positions with the SAME Camera_X carry the same Plane-B ramp by construction -- the ramp
    is a function of camX -- yet they can look completely different, because how much of
    Plane B the player can actually SEE depends on how much Plane A covers. A sheared
    background behind a solid foreground is invisible, and "invisible" is a property of the
    level's art at that spot, not of the parallax engine.

    `emulator/pixel_attribution` answers it on the REAL frame: it reports which layer won
    each pixel. It is NOT layer masking -- nothing is disabled and the frame is not
    re-rendered, so this does not hit the "mask-then-render is blind" failure, which fails
    by showing a clean picture.
    """
    layers, sc, authored, vs, k = layers_from_scene(scene)
    sym = parse_lst(lst)
    require_symbols(sym, lst)
    lo, hi, step = rowspec
    out = []
    for (px, py) in spots:
        async with Server(rom, "attr%d_%d" % (px, py)) as srv:
            b = srv.client
            await boot_into_section4(b, sym, lst, px, py)
            cam_x = int.from_bytes(await rd(b, sym["Camera_X"], 4), "big") >> 16
            cam_y = int.from_bytes(await rd(b, sym["Camera_Y"], 4), "big") >> 16
            per_band = {}
            for (i, top, end, fa, fb, to) in band_spans(layers):
                if to is None:
                    continue
                tally = {}
                for y in range(max(top, lo), min(end, hi), step):
                    for x in range(0, SCREEN_W, cols):
                        a = await c(b, "emulator/pixel_attribution", {"x": x, "y": y})
                        w = a.get("winner")
                        if isinstance(w, dict):
                            w = w.get("layer")
                        tally[str(w)] = tally.get(str(w), 0) + 1
                per_band[top] = tally
            out.append({"warp": [px, py], "cam_x": cam_x, "cam_y": cam_y,
                        "bands": per_band})
    return out, layers


def report_attrib(rows_):
    print("\n=== phase attrib -- which layer WINS the pixels of each curve band ===")
    print("  (emulator/pixel_attribution on the real frame; nothing masked, nothing "
          "re-rendered)")
    for r in rows_:
        print("\n  warp %s  Camera (%d, %d)" % (r["warp"], r["cam_x"], r["cam_y"]))
        for top, tally in sorted(r["bands"].items()):
            tot = sum(tally.values()) or 1
            parts = ", ".join("%s %d (%.0f%%)" % (kk, vv, 100.0 * vv / tot)
                              for kk, vv in sorted(tally.items(), key=lambda t: -t[1]))
            print("     band top %s: %s" % (top, parts))


def report(samples, layers, phase):
    print(f"\n=== phase {phase} ===")
    print("  band geometry from the AUTHORED scene (v_offset 0 -> rotation is the identity):")
    for (i, top, end, fa, fb, to) in band_spans(layers):
        print("    layer %d  screen %3d..%3d  span %3d  fb %03X  curve %s"
              % (i, top, end - 1, end - top, fb, "-" if to is None else "To(%03X)" % to))
    print(f"  wrap margin PLANE_W - SCREEN_W = {PLANE_W} - {SCREEN_W} = {WRAP_MARGIN} px "
          f"(derived; a band whose excursion exceeds it shows some plane column TWICE)")
    for r in samples:
        print(f"\n  -- {r['label']}")
        print(f"     Camera ({r['cam_x']}, {r['cam_y']})  section {r['section']}  "
              f"Vscroll_BG {r['vscroll_bg']}"
              + (f"  ack {r['ack']}f" if "ack" in r else ""))
        if r.get("checks"):
            ck = r["checks"]
            print(f"     config pinned: current {ck['current_config']} "
                  f"target {ck['target_config']} transition {ck['transition_frames']} "
                  f"-> all asserted OK")
        if "config_is_sec4" in r:
            print(f"     Parallax_Current_Config {r['current_config']}  "
                  f"is the section-4 binding: {r['config_is_sec4']}")
        print(f"     Parallax_Drift_Acc pixel part per band: {r['drift_px']}")
        print(f"     derived-vs-measured  BG {r['n_bg_mismatch']}/224 lines differ, "
              f"max |delta| {r['max_abs_bg_delta']}   FG max |delta| "
              f"{r['max_abs_fg_delta']}"
              f"   (ignoring drift: {r['n_bg_mismatch_no_drift']}/224)")
        for bd in r["bands"]:
            if not bd["is_curve"]:
                continue
            print("     CURVE band %3d..%3d (span %2d, fb %s -> %s): excursion %5d px "
                  "(%.2f x margin), rate %6s px/line, duplicates %s"
                  % (bd["top"], bd["end"] - 1, bd["lines"], bd["fb"], bd["to"],
                     bd["excursion"], bd["excursion_over_margin"], bd["rate_mean"],
                     "YES" if bd["duplicates"] else "no"))
        print(f"     png {r['png']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--scene",
                    default="games/sonic4/data/editor/effects/ojz_act1_depth.json")
    ap.add_argument("--phase", choices=("play", "sweep", "attrib"),
                    required=True)
    ap.add_argument("--spots", default="2300,2300 3000,2300 3900,2300 3000,3000",
                    help="phase play: space-separated PLAYER x,y warp destinations")
    ap.add_argument("--camera-x", default="64,128,250,384,512,768,1024,1536,2048,2840,3840",
                    help="phase sweep: comma-separated camera x values")
    ap.add_argument("--warp", default="3000,2300",
                    help="phase sweep: the PLAYER position that installs the section-4 scene")
    ap.add_argument("--png-dir")
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.png_dir:
        Path(a.png_dir).mkdir(parents=True, exist_ok=True)
    for p in (a.rom, a.lst, a.scene):
        if not Path(p).is_file():
            print(f"depth_onset_probe: missing {p}", file=sys.stderr)
            return 2
    try:
        if a.phase == "play":
            spots = [tuple(int(v) for v in s.split(",")) for s in a.spots.split()]
            samples, layers = asyncio.run(run_play(a.rom, a.lst, a.scene, spots, a.png_dir))
        elif a.phase == "attrib":
            spots = [tuple(int(v) for v in q.split(",")) for q in a.spots.split()]
            rows_, layers = asyncio.run(
                run_attrib(a.rom, a.lst, a.scene, spots, 8, (0, LINES, 4)))
            report_attrib(rows_)
            if a.json:
                Path(a.json).write_text(json.dumps(rows_, indent=1))
                print("\njson -> %s" % a.json)
            return 0
        else:
            cams = [int(v) for v in a.camera_x.split(",")]
            warp = tuple(int(v) for v in a.warp.split(","))
            samples, layers = asyncio.run(
                run_sweep(a.rom, a.lst, a.scene, cams, warp, a.png_dir))
    except Setup as e:
        print(f"depth_onset_probe: UNMEASURABLE -- {e}", file=sys.stderr)
        return 2

    report(samples, layers, a.phase)
    if a.png_dir:
        for (i, top, end, fa, fb, to) in band_spans(layers):
            if to is None:
                continue
            p = str(Path(a.png_dir) / f"depth-{a.phase}-band{top}.png")
            print("  montage band %d..%d -> %s"
                  % (top, end - 1, montage(samples, top, end, p,
                                           f"layer top {top}, span {end - top}, "
                                           f"fb {fb:03X} -> To({to:03X})")))
    if a.json:
        thin = []
        for r in samples:
            t = {k: v for k, v in r.items() if k != "pix"}
            thin.append(t)
        Path(a.json).write_text(json.dumps(thin, indent=1))
        print(f"\njson -> {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
