#!/usr/bin/env python3
"""sec5_band_witness — does an AUTHORED, sidecar-bound raster band reach the screen?

THE SUBJECT. EFFECTS-W1 item 1 step 6 (aeon c9a462be) bound a preset document to OJZ act 1
section 5 through `section_5.meta.json`'s `rasterRef`, and its own commit message says
"NOT VERIFIED: nothing has been seen on screen". This instrument is that verification, in
the shape aurora and aeon agreed: a frame with the band edge inside the section (the
picture), the same section with the sidecar removed (the control), and CRAM sampled by
scanline on two independent bound instances plus the control, where the two bound tables
must agree byte for byte.

WHAT IT MEASURES, AND WHAT IT DOES NOT.
  * It measures the AUTHORED BINDING: it warps the player into the section and lets the
    engine's own crossing path (Debug_Warp_Consume step 7 -> Parallax_CheckBoundary ->
    Effects_InstallPreset -> Raster_Install -> Raster_VBlank) install whatever that section
    binds. It never pokes Raster_Pending. `tools/band_witness.py` installs a demo program
    by hand; this one is different on purpose, because the question is whether the
    sidecar reaches the screen, not whether the raster tier works.
  * `run_to_scanline` is polling-based and can land a line or two past its target, so the
    sample lines are chosen well inside and well outside the band; the transition line is
    NOT pinned here (the build-time arm decode, effects_gates PIN 5, is what pins that).
  * It samples ONE CRAM entry, the one the preset names. A band that also touched a
    neighbour would pass.
  * The frame capture is a picture for a human to read; the CRAM table is the measurement.

EVERY EXPECTATION IS DERIVED, NEVER TYPED. Band lines, the CRAM line/entry and the colour
come from PARSING the preset document the sidecar names; the label the engine must have
installed comes from the GENERATED chooser (`ojz_act1_sec_raster`) so a stale generated
tree is caught rather than trusted; the section geometry comes from `SECTION_SIZE_SHIFT`,
`SCREEN_WIDTH`/`SCREEN_HEIGHT` (engine/system/constants.emp) and `GRID_W`/`GRID_H`
(the act descriptor). The base colour is the one thing no document states, so it is
MEASURED off the out-of-band lines and must be uniform across them.

THIS IS AN INSTRUMENT, NOT A GATE, and it REFUSES rather than guesses on:
  * the served ROM not matching the file on disk (the stale-shim classic)
  * the sidecar and the generated chooser disagreeing about whether the section is bound
  * a warp that never acks, or that the engine clamped away from the requested point
  * `Raster_Pending` still staged after the settle (VBlank never consumed the install)
  * `Raster_Program` not being the label the chooser binds (bound) / not 0 (control)
  * the camera's section (recomputed from Camera_X/Y) disagreeing with the engine's own
    Parallax_Prev_Sec_X/Y, or either disagreeing with the requested section
  * `run_to_scanline` reporting `reached: false`
  * VACUITY (bound runs): every in-band sample identical to every out-of-band sample means
    the CRAM instrument is frame-latched and blind to a mid-frame write. UNMEASURABLE, not
    green. A base colour equal to the authored colour is refused for the same reason.
  * a frame whose `source` is not "raster"

USAGE
    python3 tools/sec5_band_witness.py --rom s4.debug.bin --lst s4.debug.lst \
        --label bound-A --out-dir docs/research/reference_captures/2026-08-30-sec5-band
    python3 tools/sec5_band_witness.py --rom s4.debug.control.bin --lst s4.debug.control.lst \
        --label control --expect-unbound --out-dir ...

Exit codes: 0 measured and every line matched its derived expectation; 1 measured and at
least one line did not; 2 REFUSED (unmeasurable — nothing about the band follows).
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/, for suite_paths
from suite_paths import add_client_path  # noqa: E402
add_client_path()  # the Aether client, resolved from the suite root; loud if absent
from aether import BusClient  # noqa: E402
from aether_instance import AetherInstance  # noqa: E402
from fg_left_edge_capture import grab, write_png  # noqa: E402  (grab insists source == "raster")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACT_DIR = os.path.join("games", "sonic4", "data", "editor", "ojz", "act1")
PRESETS_DIR = os.path.join("games", "sonic4", "data", "editor", "effects", "presets")
GENERATED = os.path.join("games", "sonic4", "data", "generated", "ojz", "act1", "effects_scenes.emp")
DESCRIPTOR = os.path.join("games", "sonic4", "data", "levels", "ojz", "act1", "act_descriptor.emp")
CONSTANTS = os.path.join("engine", "system", "constants.emp")
CHOOSER = "ojz_act1_sec_raster"
RASTER_REF_KEY = "rasterRef"            # empyrean AURORA_EFFECTS_SCHEMA §3.1; effects_gen.ACT_RASTER_REF_KEY
ACTIVE_H = 224
DEFAULT_LINES = "8,20,40,56,72,96,150"

EXIT_OK, EXIT_MISMATCH, EXIT_REFUSED = 0, 1, 2


class Refused(SystemExit):
    def __init__(self, why: str):
        super().__init__(EXIT_REFUSED)
        self.why = why


def refuse(why: str) -> "Refused":
    print(f"REFUSED: {why}")
    return Refused(why)


# ----------------------------------------------------------------------------- derivations

def parse_const(text: str, name: str, where: str) -> int:
    m = re.search(r"^\s*(?:pub\s+)?const\s+" + re.escape(name) + r"\s*=\s*(\$?[0-9A-Fa-f]+)", text, re.M)
    if not m:
        raise refuse(f"could not parse `{name}` out of {where}")
    v = m.group(1)
    return int(v[1:], 16) if v.startswith("$") else int(v)


def geometry(repo: str) -> dict:
    consts = open(os.path.join(repo, CONSTANTS), encoding="utf-8").read()
    desc = open(os.path.join(repo, DESCRIPTOR), encoding="utf-8").read()
    shift = parse_const(consts, "SECTION_SIZE_SHIFT", CONSTANTS)
    return {
        "shift": shift,
        "size": 1 << shift,
        "screen_w": parse_const(consts, "SCREEN_WIDTH", CONSTANTS),
        "screen_h": parse_const(consts, "SCREEN_HEIGHT", CONSTANTS),
        "grid_w": parse_const(desc, "GRID_W", DESCRIPTOR),
        "grid_h": parse_const(desc, "GRID_H", DESCRIPTOR),
    }


def sidecar_ref(repo: str, sec: int):
    path = os.path.join(repo, ACT_DIR, f"section_{sec}.meta.json")
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    return doc.get(RASTER_REF_KEY), path


def load_preset(repo: str, pid: str) -> tuple[dict, str]:
    d = os.path.join(repo, PRESETS_DIR)
    for name in sorted(os.listdir(d)):
        if not name.endswith(".json"):
            continue
        p = os.path.join(d, name)
        with open(p, encoding="utf-8") as fh:
            doc = json.load(fh)
        if doc.get("id") == pid:
            return doc, p
    raise refuse(f"{RASTER_REF_KEY} {pid!r} names no preset document under {PRESETS_DIR}")


def expectation(preset: dict, where: str) -> dict:
    """The single-colour, single-band shape this instrument can measure — parsed, not typed."""
    bands = preset.get("bands")
    if not isinstance(bands, list) or len(bands) != 1:
        raise refuse(f"{where}: this instrument measures exactly ONE band; the document has "
                     f"{len(bands) if isinstance(bands, list) else 'no'} — extend it, do not guess")
    band = bands[0]
    on = band.get("on", {})
    if list(on.keys()) != ["cram"]:
        raise refuse(f"{where}: band.on must be a lone `cram` op for this instrument, got {list(on.keys())}")
    cram = on["cram"]
    colours = cram["colours"]
    if len(colours) != 1:
        raise refuse(f"{where}: this instrument samples ONE entry; the op streams {len(colours)} colours")
    addr = int(cram["addr"])
    return {
        "preset_id": preset["id"],
        "top": int(band["top"]),
        "bot": int(band["bot"]),
        "cram_addr": addr,
        "cram_line": addr >> 5,           # 32 bytes per CRAM line
        "cram_entry": (addr >> 1) & 15,   # 2 bytes per entry
        "colour": int(colours[0]) & 0x0EEE,
    }


def chooser_binding(repo: str, sec: int):
    """The label the GENERATED chooser binds for `sec`, or None. Read off the arm itself."""
    text = open(os.path.join(repo, GENERATED), encoding="utf-8").read()
    m = re.search(r"pub comptime fn " + CHOOSER + r"\(.*?\)\s*->\s*Label\s*\{(.*?)\n\}", text, re.S)
    if not m:
        raise refuse(f"could not find `{CHOOSER}` in {GENERATED}")
    arms = dict((int(a), b) for a, b in re.findall(r"if sec == (\d+) \{ out = (\w+) \}", m.group(1)))
    return arms.get(sec), arms


# ----------------------------------------------------------------------------- bus helpers

def _hex(s) -> int:
    s = str(s)
    return int(s[2:] if s[:2].lower() == "0x" else (s[1:] if s[:1] == "$" else s), 16)


async def lookup(c: BusClient, name: str) -> int:
    try:
        r = await c.call("emulator/lookup_symbol", {"name": name})
    except Exception as e:  # the bus raises on an unknown symbol; say which one
        raise refuse(f"symbol {name!r} does not resolve against the loaded listing: {e}")
    return _hex(r["addr"])


async def rd(c: BusClient, addr: int, length: int) -> int:
    r = await c.call("emulator/read_memory", {"addr": hex(addr), "len": length})
    return _hex(r["bytes"])


async def wr(c: BusClient, addr: int, value: int, width: int) -> None:
    await c.call("emulator/write_memory", {"addr": hex(addr), "value": value, "width": width})


async def frame_no(c: BusClient) -> int:
    return int((await c.call("emulator/status", {}))["frame"])


async def warp(c: BusClient, syms: dict, px: int, py: int) -> int:
    """Debug warp mailbox (the idiom of tools/fg_left_edge_probe.py); returns frames to ack."""
    await wr(c, syms["Warp_Req_X"], px, 2)
    await wr(c, syms["Warp_Req_Y"], py, 2)
    await wr(c, syms["Warp_Req_Flag"], 1, 1)
    for i in range(1, 121):
        await c.call("emulator/run_frames", {"frames": 1})
        if await rd(c, syms["Warp_Req_Flag"], 1) == 0:
            bx, by = await rd(c, syms["Warp_Req_X"], 2), await rd(c, syms["Warp_Req_Y"], 2)
            if (bx, by) != (px, py):
                raise refuse(f"the engine CLAMPED the warp: requested ({px}, {py}), landed ({bx}, {by}) "
                             f"— the requested point is not inside the act")
            return i
    raise refuse("Warp_Req_Flag never cleared in 120 frames — the consumer did not run "
                 "(wrong ROM shape, or not in the level state)")


# ----------------------------------------------------------------------------- the run

async def measure(sock: str, a, blob: bytes, exp: dict | None, label_name: str | None,
                  geo: dict, lines: list[int], out: dict) -> int:
    c = BusClient(socket_path=sock, client_id="sec5w", client_name="sec5_band_witness")
    await c.connect()
    st = await c.call("emulator/status", {})
    if st["romBytes"] != len(blob):
        raise refuse(f"server serves {st['romBytes']} bytes, {a.rom} is {len(blob)} — a different ROM")
    print(f"      server romPath={st['romPath']} romBytes={st['romBytes']} (matches)")

    names = ["Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag", "Raster_Program", "Raster_Pending",
             "Parallax_Prev_Sec_X", "Parallax_Prev_Sec_Y", "Camera_X", "Camera_Y", "Raster_Program_None"]
    syms = {n: await lookup(c, n) for n in names}
    want_prog = 0
    if label_name is not None:
        syms[label_name] = await lookup(c, label_name)
        want_prog = syms[label_name]
    out["symbols"] = {k: f"${v:06X}" for k, v in syms.items()}

    await c.call("emulator/run_frames", {"frames": a.settle})
    pre_prog = await rd(c, syms["Raster_Program"], 4)
    pre_sec = (await rd(c, syms["Parallax_Prev_Sec_X"], 1), await rd(c, syms["Parallax_Prev_Sec_Y"], 1))
    print(f"      after {a.settle} settle frames: Raster_Program=${pre_prog:06X} Prev_Sec={pre_sec}")

    # ---- into the section, through the engine's own crossing path ----
    col, row = a.section % geo["grid_w"], a.section // geo["grid_w"]
    px = col * geo["size"] + geo["size"] // 2
    py = row * geo["size"] + geo["size"] // 2
    acked = await warp(c, syms, px, py)
    await c.call("emulator/run_frames", {"frames": a.post_warp})
    print(f"      warp -> player ({px}, {py}) acked in {acked} frames; +{a.post_warp} frames")

    pending = await rd(c, syms["Raster_Pending"], 4)
    prog = await rd(c, syms["Raster_Program"], 4)
    cam_x = (await rd(c, syms["Camera_X"], 4)) >> 16
    cam_y = (await rd(c, syms["Camera_Y"], 4)) >> 16
    prev = (await rd(c, syms["Parallax_Prev_Sec_X"], 1), await rd(c, syms["Parallax_Prev_Sec_Y"], 1))
    # Parallax_CheckBoundary's own decompose: the section under the camera CENTRE.
    cam_sec = ((cam_x + geo["screen_w"] // 2) >> geo["shift"], (cam_y + geo["screen_h"] // 2) >> geo["shift"])
    flat = cam_sec[1] * geo["grid_w"] + cam_sec[0]
    print(f"      Camera=({cam_x}, {cam_y})  camera-centre section={cam_sec} flat={flat}  "
          f"engine Parallax_Prev_Sec={prev}  Raster_Pending=${pending:08X}  Raster_Program=${prog:06X}")
    out.update({"player": [px, py], "camera": [cam_x, cam_y], "camera_section": list(cam_sec),
                "flat_section": flat, "engine_prev_sec": list(prev),
                "raster_pending": f"${pending:08X}", "raster_program": f"${prog:06X}",
                "raster_program_want": f"${want_prog:06X}", "warp_ack_frames": acked})
    if cam_sec != (col, row) or prev != (col, row):
        raise refuse(f"section mismatch: requested ({col}, {row}), camera-centre says {cam_sec}, "
                     f"engine says {prev}")
    if pending != 0:
        raise refuse(f"Raster_Pending is still ${pending:08X} after {a.post_warp} frames — VBlank never "
                     f"consumed the install, so nothing below is the authored program")
    if prog != want_prog:
        what = f"{label_name} ${want_prog:06X}" if label_name else "0 (an empty program uninstalls)"
        raise refuse(f"Raster_Program is ${prog:06X}, not {what} — the section did not install what the "
                     f"chooser binds (Raster_Program_None is ${syms['Raster_Program_None']:06X})")

    # ---- the CRAM table ----
    cram_line, entry = (exp["cram_line"], exp["cram_entry"]) if exp else (a.cram_line, a.cram_entry)
    top, bot = (exp["top"], exp["bot"]) if exp else (None, None)
    samples = []
    for ln in lines:
        r = await c.call("emulator/run_to_scanline", {"line": ln})
        if not r.get("reached"):
            raise refuse(f"run_to_scanline({ln}) reported reached=false: {r.get('caveat', r)}")
        cr = await c.call("emulator/read_cram", {"line": cram_line})
        ent = cr["palette"][entry]
        if int(ent["line"]) != cram_line or int(ent["index"]) != entry:
            raise refuse(f"read_cram returned entry line {ent['line']} index {ent['index']}, asked "
                         f"{cram_line}/{entry}")
        raw = _hex(ent["raw"])
        in_band = (top is not None) and (top <= ln < bot)
        samples.append({"line": ln, "frame": await frame_no(c), "in_band": in_band, "raw": raw})

    outside = [s["raw"] for s in samples if not s["in_band"]]
    inside = [s["raw"] for s in samples if s["in_band"]]
    if not outside:
        raise refuse("no out-of-band sample line — the base colour cannot be measured")
    if len(set(outside)) != 1:
        raise refuse(f"the out-of-band samples disagree ({[f'${v:04X}' for v in outside]}) — the base "
                     f"is not uniform, so no expectation can be derived from it")
    base = outside[0]
    if exp is not None:
        if base == exp["colour"]:
            raise refuse(f"the measured base ${base:04X} EQUALS the authored colour — the instrument "
                         f"could not distinguish a band from no band")
        if inside and set(inside) == {base}:
            raise refuse("VACUOUS: every in-band sample reads the base colour, identical to every "
                         "out-of-band sample — either the CRAM instrument is frame-latched and blind to "
                         "a mid-frame write, or nothing fires. UNMEASURABLE, not a result.")

    mism = 0
    print(f"\n      CRAM line {cram_line} entry {entry} (byte ${cram_line * 32 + entry * 2:02X}); "
          f"measured base ${base:04X}"
          + (f"; authored band {top}..{bot - 1} colour ${exp['colour']:04X}" if exp else "; control: no band"))
    print("      line  frame  region    read    expect  verdict")
    for s in samples:
        want = exp["colour"] if (exp and s["in_band"]) else base
        ok = s["raw"] == want
        mism += 0 if ok else 1
        s["expect"] = want
        s["ok"] = ok
        print(f"      {s['line']:>4}  {s['frame']:>5}  {'IN-BAND ' if s['in_band'] else 'outside '}  "
              f"${s['raw']:04X}   ${want:04X}   {'OK' if ok else 'MISMATCH'}")
    out["base"] = base
    out["samples"] = samples
    if exp is not None:
        out["vacuity"] = f"{len(set(inside))} distinct in-band value(s) vs base ${base:04X} — not vacuous"
        print(f"      vacuity check: {out['vacuity']}")

    # ---- the picture: one COMPLETE frame the raster drew ----
    await c.call("emulator/run_frames", {"frames": 1})
    w, rows = await grab(c, 0, ACTIVE_H - 1)         # refuses unless source == "raster"
    os.makedirs(a.out_dir, exist_ok=True)
    full = os.path.join(a.out_dir, f"{a.label}-sec{a.section}-full.png")
    write_png(full, w, len(rows), rows)
    y0, y1 = a.crop_y
    x0, x1 = a.crop_x
    crop = [r[x0 * 3:x1 * 3] for r in rows[y0:y1]]
    cpath = os.path.join(a.out_dir, f"{a.label}-sec{a.section}-rows{y0}-{y1 - 1}-x{x0}-{x1 - 1}-{a.scale}x.png")
    write_png(cpath, x1 - x0, len(crop), crop, scale=a.scale)
    out["frame_png"] = {os.path.basename(full): hashlib.md5(open(full, "rb").read()).hexdigest(),
                        os.path.basename(cpath): hashlib.md5(open(cpath, "rb").read()).hexdigest()}
    out["frame_captured_at"] = await frame_no(c)
    print(f"\n      wrote {full}  ({w}x{len(rows)})  md5 {out['frame_png'][os.path.basename(full)]}")
    print(f"      wrote {cpath}  (rows {y0}..{y1 - 1}, x {x0}..{x1 - 1}, {a.scale}x)  "
          f"md5 {out['frame_png'][os.path.basename(cpath)]}")
    await c.close()
    return EXIT_MISMATCH if mism else EXIT_OK


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default=os.path.join(REPO, "s4.debug.bin"))
    ap.add_argument("--lst", default=None, help="listing; default = ROM path with .lst")
    ap.add_argument("--repo", default=REPO, help="the aeon tree whose sidecar/preset/generated files to parse")
    ap.add_argument("--section", type=int, default=5)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--expect-unbound", action="store_true",
                    help="CONTROL run: the sidecar must carry no rasterRef and the chooser no arm")
    ap.add_argument("--cram-line", type=int, default=None,
                    help="control only: CRAM line to sample (default: the bound preset's, if it still exists)")
    ap.add_argument("--cram-entry", type=int, default=None)
    ap.add_argument("--lines", default=DEFAULT_LINES)
    ap.add_argument("--settle", type=int, default=240)
    ap.add_argument("--post-warp", type=int, default=4,
                    help="frames after the ack so Raster_VBlank consumes the staged install")
    ap.add_argument("--crop-y", default="16,96", help="crop rows y0,y1 (y1 exclusive)")
    ap.add_argument("--crop-x", default="80,144",
                    help="crop columns x0,x1 (x1 exclusive); the default is a gap between OJZ trunks "
                         "at this warp, where the BACKGROUND shows and the band edge is unoccluded")
    ap.add_argument("--scale", type=int, default=6)
    a = ap.parse_args()
    a.crop_y = tuple(int(v) for v in a.crop_y.split(","))
    a.crop_x = tuple(int(v) for v in a.crop_x.split(","))
    lines = [int(v) for v in a.lines.split(",")]
    rom = os.path.abspath(a.rom)
    lst = os.path.abspath(a.lst) if a.lst else rom[:-4] + ".lst"

    blob = open(rom, "rb").read()
    crc = zlib.crc32(blob) & 0xFFFFFFFF
    print(f"ROM   {rom}\n      {len(blob)} bytes, crc32 {crc:08x}\nLST   {lst}")
    out = {"rom": rom, "rom_bytes": len(blob), "rom_crc32": f"{crc:08x}", "lst": lst, "label": a.label,
           "section": a.section, "lines": lines}

    # ---- derive everything before touching an emulator ----
    geo = geometry(a.repo)
    ref, sidecar_path = sidecar_ref(a.repo, a.section)
    label_name, arms = chooser_binding(a.repo, a.section)
    print(f"GEOM  section size {geo['size']} px (SECTION_SIZE_SHIFT {geo['shift']}), grid "
          f"{geo['grid_w']}x{geo['grid_h']}, screen {geo['screen_w']}x{geo['screen_h']}")
    print(f"BIND  {os.path.relpath(sidecar_path, a.repo)} {RASTER_REF_KEY}={ref!r}; generated chooser arms {arms}")
    out.update({"geometry": geo, "sidecar_rasterRef": ref, "chooser_arms": arms})
    exp = None
    if a.expect_unbound:
        if ref is not None or label_name is not None:
            raise refuse(f"--expect-unbound but the sidecar says {ref!r} and the chooser binds {label_name!r}")
        if a.cram_line is None or a.cram_entry is None:
            raise refuse("control run needs --cram-line/--cram-entry (there is no preset to parse them from)")
        print(f"CTRL  unbound: sampling CRAM line {a.cram_line} entry {a.cram_entry}; every line must read the base")
    else:
        if ref is None or label_name is None:
            raise refuse(f"the sidecar says {ref!r} and the chooser binds {label_name!r} — not a bound section "
                         f"(pass --expect-unbound for a control run)")
        preset, ppath = load_preset(a.repo, ref)
        exp = expectation(preset, os.path.relpath(ppath, a.repo))
        if label_name != f"EditorRaster_OJZ_Act1_{exp['preset_id']}":
            raise refuse(f"the chooser binds {label_name}, which is not the label the generator emits for "
                         f"preset {exp['preset_id']!r}")
        print(f"EXPECT {os.path.relpath(ppath, a.repo)}: band {exp['top']}..{exp['bot'] - 1} (top {exp['top']}, "
              f"bot {exp['bot']}), CRAM byte ${exp['cram_addr']:02X} = line {exp['cram_line']} entry "
              f"{exp['cram_entry']}, colour ${exp['colour']:04X}; engine must install {label_name}")
        out["expectation"] = exp
        out["binding_label"] = label_name

    inst = AetherInstance(rom, symbols=lst)
    sock = inst.start()
    rc = EXIT_REFUSED
    try:
        rc = asyncio.run(measure(sock, a, blob, exp, label_name, geo, lines, out))
    except Refused as r:
        out["refused"] = r.why
        rc = EXIT_REFUSED
    finally:
        inst.reap()
    os.makedirs(a.out_dir, exist_ok=True)
    out["exit"] = rc
    jpath = os.path.join(a.out_dir, f"{a.label}-sec{a.section}.json")
    with open(jpath, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    # The byte-exact comparable: line/region/value only (frame numbers differ between instances
    # by construction, so they are kept OUT of this table and IN the JSON).
    tpath = os.path.join(a.out_dir, f"{a.label}-sec{a.section}.cram.txt")
    with open(tpath, "w", encoding="utf-8") as fh:
        for s in out.get("samples", []):
            fh.write(f"line {s['line']:>3} {'in ' if s['in_band'] else 'out'} ${s['raw']:04X}\n")
    print(f"\n      wrote {jpath}\n      wrote {tpath}")
    verdict = {EXIT_OK: "MEASURED — every sampled line matched its derived expectation",
               EXIT_MISMATCH: "MEASURED — at least one line did NOT match (see table)",
               EXIT_REFUSED: "REFUSED — unmeasurable; nothing about the band follows"}[rc]
    print(f"\nRESULT: {verdict}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
