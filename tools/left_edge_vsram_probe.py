#!/usr/bin/env python3
"""left_edge_vsram_probe — what V-scroll does the leftmost sliver READ, frame by frame?

WHY THIS EXISTS. The owner, looking at the effects lab on master's build (2026-08-30), said
the strip at the LEFT edge of the screen "is animating differently and super fast". A
six-frame screenshot diff over his window measured the left 16 px changing 1.27x as often
as the body — elevated, not "super fast" — and could not say WHY. DEFERRED_WORK books the
sighting as measured-not-explained and names the next instrument: NOT another pixel diff,
but a sample of VSRAM's entries across frames against plane A's own scroll, because what
the leading sliver shows is a VSRAM question.

WHAT THE SLIVER READS (the rule this probe is built on). With per-column V-scroll on (VDP
reg $0B bit 2) and a plane's HScroll off the 16-px grain, THAT plane's leading `hscroll &
15` px render at `VSRAM[$4C] & VSRAM[$4E]` — column-pair 19's two words ANDed, the same
value for both planes, H40 only (Eke-Eke's hardware test, PAL MD2 2010; implemented
character-for-character in Genesis Plus GX and in Oracle's `plane_vscroll`). Oracle's
`plane_sample` passes each plane its OWN per-line hscroll, so the gate is evaluated per
plane per line: plane B's left edge takes the AND value on exactly the lines where plane
B's hscroll is off-grain. Since the d-41 borrow, `$4E` is overwritten with camY, so the AND
is camY — right for plane A (which IS at camY) and a displacement of `camY - Vscroll_BG`
for plane B (which is vertically locked on every per-column scene).

WHAT IT SAMPLES, per frame, for N consecutive frames, at each scene and camera position:
  * Camera_X / Camera_Y (pixel halves of the 16.16 words) and `Camera_X & 15`
  * the full 40-word VSRAM (space "vsram")                       -- what the VDP reads
  * Parallax_Vscroll_Column_Buf (80 B RAM mirror)                -- what the producer wrote
  * Hscroll_Buffer (896 B: 224 lines x {FG word, BG word})       -- both planes' per-line hscroll
  * the VDP's H-scroll table from VRAM at (reg $0D & $3F) << 10  -- what the VDP reads
  * Parallax_V_Deform_Phase_BG, Parallax_Current_Vscroll_BG
and derives: AND = VSRAM[$4C] & VSRAM[$4E] & $7FF (the sliver's value), pair 0's two words,
the per-frame deltas of each against Camera_Y's delta, and — the part the VSRAM-only
framing would miss — the SET OF LINES on which each plane's hscroll is off-grain, and how
many lines enter or leave that set between consecutive frames. A plane-B sliver that
exists on a different set of rows every frame is a strip whose CONTENT changes every frame
without any VSRAM word moving.

THREE POSITIONS PER SCENE: the scene's default camera, a warp that makes `Camera_X & 15`
== 8 (a wide plane-A sliver), and that same position with DOWN held (camera Y in motion,
so the rate comparison has a nonzero reference).

CORROBORATION, never the verdict: one raster-sourced frame per position (full + 6x crop of
x 0..31), one more with plane A and sprites masked so plane B's edge is visible alone, and
`pixel_attribution` grids — plane-A opacity at x 0..15 (+16, 24) over rows 96..216 (the
still-owed d-32 re-measure), and plane B's winning TILE at x=4 vs x=20 on the same rows.

LOUD ON UNMEASURABLE. Served ROM not matching the file; a symbol that will not resolve;
the scene cursor not landing where driven; reg $0B bit 2 clear at a sample point (the
DEBUG warp clears it, so the scene is re-installed after every warp and the bit re-read);
the warp never acking; a capture whose `source != "raster"`. Each is a refusal with its
text, never a zero and never a green. The one thing it does NOT refuse on is a warp that
lands somewhere other than requested (the consumer clamps) — it reports where it landed and
labels the position by the `Camera_X & 15` it actually measured.

USAGE
    python3 tools/left_edge_vsram_probe.py --rom s4.debug.bin --lst s4.debug.lst \
        --scenes 12,13,14 --frames 32 --out-dir docs/research/reference_captures/X
    (writes <out-dir>/probe.json with every raw sample, and the PNGs)

RUN IT FOREGROUND. It boots a headless emulator via tools/aether_instance.py — never the
owner's socket.
"""
import argparse
import asyncio
import json
import os
import struct
import subprocess
import sys
import time
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aether_instance import AetherInstance                      # noqa: E402
from aether import BusClient                                    # noqa: E402
import fg_left_edge_gate as G                                   # noqa: E402
import fg_left_edge_capture as C                                # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINES = 224
VSRAM_BYTES = 80                     # 40 words = 20 column-pairs x {A, B}
HS_TABLE_BYTES = LINES * 4           # 224 lines x {A word, B word}
VDP_HSCROLL_REG = 0x0D
ROWS = list(range(96, 216 + 1, 8))
MIN_FRAMES = 8                       # fewer valid frames than this is a refusal, not a short table
D32_COLS = list(range(0, 16)) + [16, 24]

SYMBOLS = ("Debug_Scene_Index", "Camera_X", "Camera_Y", "VDP_Shadow_Table",
           "Parallax_Vscroll_Column_Buf", "Hscroll_Buffer", "Parallax_V_Deform_Phase_BG",
           "Parallax_Current_Vscroll_BG", "Parallax_Transition_Frames",
           "Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag")


def u16s(b):
    return list(struct.unpack(f">{len(b) // 2}H", b))


def s16(v):
    return v - 0x10000 if v & 0x8000 else v


def s11(v):
    """VSRAM words are 11 bits wide; a delta between two of them is signed in that domain."""
    v &= G.VSRAM_MASK
    return v - 0x800 if v & 0x400 else v


async def read_space(c, space, addr, length):
    r = await c.call("emulator/read", {"space": space, "addr": hex(addr), "len": length})
    return bytes.fromhex(str(r["bytes"]).removeprefix("0x"))


async def read_bus_bytes(c, addr, length):
    return await read_space(c, "bus", addr, length)


async def step_scene_back(c):
    """START held, LEFT pressed on one frame — the mirror of G.step_scene."""
    await c.call("emulator/play_input", {
        "rows": [
            {"start": 0, "end": 2, "buttons": ["start"]},
            {"start": 2, "end": 3, "buttons": ["start", "left"]},
            {"start": 3, "end": 8, "buttons": ["start"]},
        ],
        "maxFrames": 8,
    })
    await c.call("emulator/release_all", {})
    await c.call("emulator/run_frames", {"frames": 4})


async def settle_transition(c, syms, limit=300):
    """Run until Parallax_Transition_Frames reads 0 (the lerp is over), then 30 more."""
    for _ in range(limit):
        tf = await G.read_bus(c, addr=syms["Parallax_Transition_Frames"], length=1)
        if tf == 0:
            await c.call("emulator/run_frames", {"frames": 30})
            return
        await c.call("emulator/run_frames", {"frames": 1})
    raise SystemExit(f"UNMEASURABLE: Parallax_Transition_Frames never reached 0 in {limit} frames")


async def drive_cursor(c, syms, index):
    for _ in range(40):
        at = await G.read_bus(c, addr=syms["Debug_Scene_Index"], length=1)
        if at == index:
            break
        await G.step_scene(c)
    else:
        raise SystemExit(f"UNMEASURABLE: could not drive the scene cursor to {index}")


async def reinstall_scene(c, syms, index):
    """The DEBUG warp re-applies the section's own scene while the cursor still reads
    `index`; step back one and forward one so SCENES[index] is installed again."""
    await step_scene_back(c)
    await G.step_scene(c)
    at = await G.read_bus(c, addr=syms["Debug_Scene_Index"], length=1)
    if at != index:
        raise SystemExit(f"UNMEASURABLE: after back+forward the cursor reads {at}, wanted {index}")


async def assert_subject(c, syms, index):
    at = await G.read_bus(c, addr=syms["Debug_Scene_Index"], length=1)
    if at != index:
        raise SystemExit(f"UNMEASURABLE scene {index}: cursor reads {at} at the sample point")
    mode3 = await G.read_bus(c, addr=syms["VDP_Shadow_Table"] + G.VDP_MODE3_OFF, length=1)
    if not mode3 & G.VDP_MODE3_PERCOL:
        raise SystemExit(f"UNMEASURABLE scene {index}: VDP reg $0B reads ${mode3:02X}, bit 2 "
                         f"(per-column V-scroll) CLEAR at the sample point — the sliver quirk "
                         f"cannot occur, so nothing here measures the subject")
    return mode3


async def camera(c, syms):
    cx = await G.read_bus(c, addr=syms["Camera_X"], length=4)
    cy = await G.read_bus(c, addr=syms["Camera_Y"], length=4)
    return (cx >> 16) & 0xFFFF, (cy >> 16) & 0xFFFF


async def warp(c, syms, px, py):
    """The mailbox warp of tools/fg_left_edge_probe.py, with the symbols pre-resolved."""
    await c.call("emulator/write_memory", {"addr": hex(syms["Warp_Req_X"]), "value": px, "width": 2})
    await c.call("emulator/write_memory", {"addr": hex(syms["Warp_Req_Y"]), "value": py, "width": 2})
    await c.call("emulator/write_memory", {"addr": hex(syms["Warp_Req_Flag"]), "value": 1, "width": 1})
    for i in range(1, 121):
        await c.call("emulator/run_frames", {"frames": 1})
        if await G.read_bus(c, addr=syms["Warp_Req_Flag"], length=1) == 0:
            bx = await G.read_bus(c, addr=syms["Warp_Req_X"], length=2)
            by = await G.read_bus(c, addr=syms["Warp_Req_Y"], length=2)
            await c.call("emulator/run_frames", {"frames": 30})
            return i, bx, by
    raise SystemExit("UNMEASURABLE: Warp_Req_Flag never cleared in 120 frames — the consumer "
                     "did not run (wrong ROM shape, or not in the level state)")


async def sample_frame(c, syms):
    cx, cy = await camera(c, syms)
    vs = u16s(await read_space(c, "vsram", 0, VSRAM_BYTES))
    buf = u16s(await read_bus_bytes(c, syms["Parallax_Vscroll_Column_Buf"], VSRAM_BYTES))
    hs_ram = u16s(await read_bus_bytes(c, syms["Hscroll_Buffer"], HS_TABLE_BYTES))
    reg0d = await G.read_bus(c, addr=syms["VDP_Shadow_Table"] + VDP_HSCROLL_REG, length=1)
    hs_vram = u16s(await read_space(c, "vram", (reg0d & 0x3F) << 10, HS_TABLE_BYTES))
    phase = await G.read_bus(c, addr=syms["Parallax_V_Deform_Phase_BG"], length=2)
    vbg = await G.read_bus(c, addr=syms["Parallax_Current_Vscroll_BG"], length=2)
    st = await c.call("emulator/status", {})
    reg0b = await G.read_bus(c, addr=syms["VDP_Shadow_Table"] + G.VDP_MODE3_OFF, length=1)
    a19, b19 = vs[38], vs[39]
    hsA = hs_vram[0::2]
    hsB = hs_vram[1::2]
    offA = [i for i in range(LINES) if hsA[i] & 15]
    offB = [i for i in range(LINES) if hsB[i] & 15]
    return {
        "frame": st["frame"], "reg0b": reg0b,
        "cam_x": cx, "cam_y": cy, "sliver_w": cx & 15,
        "vsram": vs, "buf": buf,
        "hs_vram_A": hsA, "hs_vram_B": hsB,
        "hs_ram_A": hs_ram[0::2], "hs_ram_B": hs_ram[1::2],
        "reg0d": reg0d, "phase_bg": phase, "vscroll_bg": vbg,
        "a19": a19, "b19": b19, "and": (a19 & b19) & G.VSRAM_MASK,
        "a0": vs[0], "b0": vs[1],
        "offA": offA, "offB": offB,
    }


def ranges(lines):
    out, start, prev = [], None, None
    for l in lines:
        if start is None:
            start = prev = l
        elif l == prev + 1:
            prev = l
        else:
            out.append((start, prev))
            start = prev = l
    if start is not None:
        out.append((start, prev))
    return out


def fmt_ranges(lines, limit=6):
    rs = ranges(lines)
    s = ", ".join(f"{a}" if a == b else f"{a}-{b}" for a, b in rs[:limit])
    return s + (f", … ({len(rs)} runs)" if len(rs) > limit else "")


async def sample_run(c, syms, index, label, frames, hold=None):
    """N frames, one sample per frame. `hold` = a button held across every frame."""
    mode3 = await assert_subject(c, syms, index)
    out, stopped = [], None
    for _ in range(frames):
        if hold:
            await c.call("emulator/play_input",
                         {"rows": [{"start": 0, "end": 1, "buttons": [hold]}], "maxFrames": 1})
        else:
            await c.call("emulator/run_frames", {"frames": 1})
        s = await sample_frame(c, syms)
        if not s["reg0b"] & G.VDP_MODE3_PERCOL:
            # Travel can cross a section boundary, which re-applies THAT section's scene and
            # clears bit 2. The frames before it are the subject; this one is not.
            stopped = (f"reg $0B read ${s['reg0b']:02X} (bit 2 CLEAR) on frame {s['frame']} at "
                       f"camera ({s['cam_x']},{s['cam_y']}) — a section crossing re-applied the "
                       f"section's own scene; the run keeps its {len(out)} frames before that")
            break
        out.append(s)
    if hold:
        await c.call("emulator/release_all", {})
    if len(out) < MIN_FRAMES:
        raise SystemExit(f"UNMEASURABLE scene {index} / {label}: only {len(out)} frames with bit 2 "
                         f"set ({stopped})")
    mode3_end = out[-1]["reg0b"]
    return {"label": label, "scene": index, "reg0b_start": mode3, "reg0b_end": mode3_end,
            "stopped": stopped, "frames": out}


def print_run(run):
    fr = run["frames"]
    print(f"\n  --- scene {run['scene']} / {run['label']}: {len(fr)} frames, "
          f"reg$0B=${run['reg0b_start']:02X}..${run['reg0b_end']:02X} ---")
    if run.get("stopped"):
        print(f"    STOPPED EARLY: {run['stopped']}")
    print("    f     camX camY w |  A19  B19  AND |   A0   B0 | bufA0 bufB0 bufB19 | phB vBG | "
          "#offA #offB dB(in/out) | dCamY dAND dA0 dB0")
    prev = None
    for s in fr:
        def d(k, wide=False):
            if prev is None:
                return ""
            return f"{(s16 if wide else s11)(s[k] - prev[k]):+d}"
        if prev is None:
            dio = ""
        else:
            pa, pb = set(prev["offB"]), set(s["offB"])
            dio = f"{len(pb - pa)}/{len(pa - pb)}"
        print(f"    {s['frame']:>5} {s['cam_x']:>5} {s['cam_y']:>4} {s['sliver_w']:>2} | "
              f"{s['a19']:04X} {s['b19']:04X} {s['and']:03X} | {s['a0']:04X} {s['b0']:04X} | "
              f"{s['buf'][0]:04X}  {s['buf'][1]:04X}  {s['buf'][39]:04X}  | "
              f"{s['phase_bg']:>3} {s16(s['vscroll_bg']):>3} | "
              f"{len(s['offA']):>4} {len(s['offB']):>4}  {dio:<9} | "
              f"{d('cam_y', True):>5} {d('and'):>4} {d('a0'):>3} {d('b0'):>3}")
        prev = s
    last = fr[-1]
    print(f"    plane-A off-grain lines (last frame): {fmt_ranges(last['offA']) or 'none'}")
    print(f"    plane-B off-grain lines (last frame): {fmt_ranges(last['offB']) or 'none'}")
    hsb = sorted(set(last['hs_vram_B']))
    print(f"    distinct plane-B hscroll values (last frame): {len(hsb)}: "
          f"{' '.join(f'{v:04X}' for v in hsb[:12])}{' …' if len(hsb) > 12 else ''}")
    hist = {}
    for v in last["hs_vram_B"]:
        hist[v & 15] = hist.get(v & 15, 0) + 1
    print("    plane-B sliver width under the hardware rule (hscroll & 15), lines per width "
          "(last frame): " + " ".join(f"{k}px:{n}" for k, n in sorted(hist.items())))
    mism = sum(1 for s in fr if s["hs_vram_A"] != s["hs_ram_A"] or s["hs_vram_B"] != s["hs_ram_B"])
    bmis = sum(1 for s in fr if s["vsram"] != [w & G.VSRAM_MASK for w in s["buf"]])
    print(f"    RAM mirror vs VDP copy at the sample point: hscroll differs on {mism}/{len(fr)} "
          f"frames, vsram (11-bit) differs on {bmis}/{len(fr)} frames")


async def d32_grid(c):
    grid = await G.sample_plane(c, "planeA", D32_COLS, ROWS)
    return {f"{x},{y}": v for (x, y), v in grid.items()}


def print_d32(grid, cam):
    print(f"\n    d-32 plane-A opacity, Camera_X={cam[0]} (&15={cam[0] & 15}) Camera_Y={cam[1]}   "
          f"(# opaque, . transparent, ? absent)   x = 0..15, then 16, 24")
    for y in ROWS:
        cells = "".join(("#" if grid[f"{x},{y}"] is True else
                         ("." if grid[f"{x},{y}"] is False else "?")) for x in D32_COLS[:16])
        tail = "".join(("#" if grid[f"{x},{y}"] is True else
                        ("." if grid[f"{x},{y}"] is False else "?")) for x in D32_COLS[16:])
        print(f"      y={y:<4} {cells}  {tail}")
    counts = [sum(1 for y in ROWS if grid[f'{x},{y}'] is True) for x in D32_COLS]
    print(f"      opaque rows per column (of {len(ROWS)}): " +
          " ".join(f"{n}" for n in counts[:16]) + f"  | x16={counts[16]} x24={counts[17]}")


async def plane_b_tiles(c, sample):
    """Plane B's winning tile at x=4 (inside a possible sliver) vs x=20 (pair 0), with plane A
    and sprites masked so plane B is the winner wherever it is opaque."""
    for layer in ("planeA", "sprites", "window"):
        await c.call("emulator/set_layer_enabled", {"layer": layer, "enabled": False})
    rows = []
    try:
        for y in ROWS:
            r4 = await c.call("emulator/pixel_attribution", {"x": 4, "y": y})
            r20 = await c.call("emulator/pixel_attribution", {"x": 20, "y": y})
            t4 = r4.get("cell", {}).get("tile")
            t20 = r20.get("cell", {}).get("tile")
            rows.append({"y": y, "hsB": sample["hs_vram_B"][y], "offgrain": bool(sample["hs_vram_B"][y] & 15),
                         "tile_x4": t4, "tile_x20": t20,
                         "winner_x4": r4["winner"].get("layer"), "winner_x20": r20["winner"].get("layer")})
    finally:
        for layer in ("planeA", "sprites", "window"):
            await c.call("emulator/set_layer_enabled", {"layer": layer, "enabled": True})
    return rows


def print_tiles(rows, sample):
    disp = (sample["and"] - sample["vscroll_bg"]) & 0x1FF
    print(f"\n    plane B alone (plane A + sprites masked): winning tile at x=4 vs x=20; "
          f"predicted sliver displacement = AND - Vscroll_BG = ${sample['and']:03X} - "
          f"{s16(sample['vscroll_bg'])} = {disp} px (mod 512)")
    print("      y    hsB   off-grain  tile@x4  tile@x20  winners")
    for r in rows:
        t4 = "-" if r["tile_x4"] is None else f"${r['tile_x4']:03X}"
        t20 = "-" if r["tile_x20"] is None else f"${r['tile_x20']:03X}"
        print(f"      {r['y']:<4} {r['hsB']:04X}  {'YES' if r['offgrain'] else 'no ':<9}  "
              f"{t4:<8} {t20:<8}  {r['winner_x4']}/{r['winner_x20']}")


async def grab_state_render(c, y0, y1, chunk=16):
    """The masked twin of C.grab: with any layer masked the server renders per line from the
    paused machine's VDP state and reports `stateRender` (engine.rs `framebuffer()` returns
    the retained raster only when the mask is all-on). ACCEPTED here, LABELLED here, and
    never used for the composed capture, which stays raster-asserted."""
    out, width, sources = [], None, set()
    y = y0
    while y <= y1:
        n = min(chunk, y1 - y + 1)
        r = await c.call("emulator/scanlines", {"startLine": y, "count": n})
        sources.add(r.get("source"))
        for row in r["rows"]:
            width = row["width"]
            out.append(bytes.fromhex(str(row["rgb"]).removeprefix("0x")))
        y += n
    return width, out, sources


async def capture(c, out_dir, name, scale, masked=False):
    if masked:
        w, rows, sources = await grab_state_render(c, 0, LINES - 1)
        print(f"    (masked capture source(s): {sorted(sources)} — a state render, not the raster)")
    else:
        w, rows = await C.grab(c, 0, LINES - 1)
    full = os.path.join(out_dir, f"{name}-full.png")
    C.write_png(full, w, len(rows), rows)
    crop = [r[0:32 * 3] for r in rows]
    left = os.path.join(out_dir, f"{name}-left.png")
    C.write_png(left, 32, len(crop), crop, scale=scale)
    return full, left, b"".join(rows)


async def capture_pair(c, out_dir, name, scale):
    """Composed frame, then the same machine one frame on with plane A + sprites masked."""
    full, left, composed = await capture(c, out_dir, name, scale)
    print(f"    wrote {left}  (x 0..31, {scale}x)  and {full}")
    for layer in ("planeA", "sprites", "window"):
        await c.call("emulator/set_layer_enabled", {"layer": layer, "enabled": False})
    try:
        bfull, bleft, bonly = await capture(c, out_dir, name + "-planeB-stateRender", scale,
                                            masked=True)
    finally:
        for layer in ("planeA", "sprites", "window"):
            await c.call("emulator/set_layer_enabled", {"layer": layer, "enabled": True})
    same = composed == bonly
    verdict = ("IDENTICAL to the composed frame — treat as NOT a plane-B-only picture" if same
               else "differs from the composed frame")
    print(f"    wrote {bleft}  (plane B alone, STATE RENDER of the paused machine; {verdict})")
    return [full, left, bfull, bleft]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default=os.path.join(REPO, "s4.debug.bin"))
    ap.add_argument("--lst", default=None)
    ap.add_argument("--scenes", default="12,13,14")
    ap.add_argument("--frames", type=int, default=32)
    ap.add_argument("--settle", type=int, default=240)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--scale", type=int, default=6)
    ap.add_argument("--warp-dy", default="0,96,192,288,384",
                    help="camera-Y offsets to try for the warp position until plane A reaches the edge")
    a = ap.parse_args()

    rom = os.path.abspath(a.rom)
    lst = a.lst or rom[:-4] + ".lst"
    scenes = [int(s) for s in a.scenes.split(",") if s.strip()]
    a.warp_dy = [int(v) for v in a.warp_dy.split(",") if v.strip()]
    blob = open(rom, "rb").read()
    crc = zlib.crc32(blob) & 0xFFFFFFFF
    print(f"ROM   {rom}\n      {len(blob)} bytes, crc32 {crc:08x}\n      scenes {scenes}, {a.frames} frames per run")
    print(f"uptime: {subprocess.run(['uptime'], capture_output=True, text=True).stdout.strip()}")
    os.makedirs(a.out_dir, exist_ok=True)
    t0 = time.monotonic()
    inst = AetherInstance(rom, symbols=lst)
    sock = inst.start()
    report = {"rom": rom, "rom_bytes": len(blob), "crc32": f"{crc:08x}", "scenes": {}}

    async def body():
        c = BusClient(sock)
        await c.connect()
        st = await c.call("emulator/status", {})
        if st["romBytes"] != len(blob):
            raise SystemExit(f"UNMEASURABLE: server serves {st['romBytes']} bytes, {rom} is {len(blob)}")
        print(f"      server romPath={st['romPath']} romBytes={st['romBytes']} (matches)")
        syms = {n: await G.lookup(c, n) for n in SYMBOLS}
        print("      symbols: " + " ".join(f"{k}=${v:06X}" for k, v in syms.items()))
        await c.call("emulator/run_frames", {"frames": a.settle})
        boot_cam = await camera(c, syms)
        report["boot_camera"] = list(boot_cam)
        print(f"      boot camera after {a.settle} frames: {boot_cam}")

        for index in scenes:
            sc = report["scenes"][str(index)] = {"positions": {}}
            await drive_cursor(c, syms, index)
            # Every scene's "default" is the BOOT camera, not wherever the previous scene's
            # runs left the player: warp back (which clears bit 2), then re-install the scene.
            n, bx, by = await warp(c, syms, boot_cam[0] + 160, boot_cam[1] + 144)
            await reinstall_scene(c, syms, index)
            await settle_transition(c, syms)
            print(f"\n  scene {index}: warp to boot camera acked in {n} frames; player=({bx},{by})")

            # ---- position 1: the scene's own default camera -------------------------
            pos = sc["positions"]["default"] = {}
            run = await sample_run(c, syms, index, "default", a.frames)
            print_run(run)
            pos["run"] = run
            cam = await camera(c, syms)
            pos["d32"] = await d32_grid(c)
            print_d32(pos["d32"], cam)
            last = run["frames"][-1]
            pos["tiles"] = await plane_b_tiles(c, last)
            print_tiles(pos["tiles"], last)
            pos["pngs"] = await capture_pair(c, a.out_dir, f"scene{index}-default", a.scale)

            # ---- position 2: warp so Camera_X & 15 == 8, at a Y where plane A reaches the
            #      left edge (d-32 needs ground there; the default Y is sky, measured) -----
            cx, cy = cam
            want_cx = cx + 256 + ((8 - cx) & 15)
            attempts = []
            for dy in a.warp_dy:
                n, bx, by = await warp(c, syms, want_cx + 160, cy + dy + 144)
                await reinstall_scene(c, syms, index)      # the DEBUG warp clears reg $0B bit 2
                await settle_transition(c, syms)
                cx2, cy2 = await camera(c, syms)
                ref = await G.sample_plane(c, "planeA", [16, 24], ROWS)
                nref = sum(1 for v in ref.values() if v is True)
                attempts.append({"dy": dy, "ack_frames": n, "player": [bx, by],
                                 "camera": [cx2, cy2], "planeA_ref_opaque": nref})
                print(f"\n  warp dy={dy}: acked in {n} frames; clamped player=({bx},{by}); camera "
                      f"({cx2},{cy2}), Camera_X & 15 = {cx2 & 15} (wanted 8); plane-A opaque "
                      f"cells at x=16/24 over rows 96..216: {nref}/{2 * len(ROWS)}")
                if nref >= 3:
                    break
            else:
                print("  NOTE: no tried warp Y put plane-A content at the left edge; the d-32 grid "
                      "below is measured where the mechanism has nothing to act on and says "
                      "NOTHING about the glitch")
            label = f"warp(&15={cx2 & 15})"
            pos = sc["positions"]["warp"] = {"warp_attempts": attempts}
            run = await sample_run(c, syms, index, label, a.frames)
            print_run(run)
            pos["run"] = run
            cam2 = await camera(c, syms)
            pos["d32"] = await d32_grid(c)
            print_d32(pos["d32"], cam2)
            last = run["frames"][-1]
            pos["tiles"] = await plane_b_tiles(c, last)
            print_tiles(pos["tiles"], last)
            pos["pngs"] = await capture_pair(c, a.out_dir, f"scene{index}-warp", a.scale)

            # ---- position 3: same place, DOWN held so Camera_Y moves ----------------
            pos = sc["positions"]["moving"] = {}
            run = await sample_run(c, syms, index, "warp + DOWN held", a.frames, hold="down")
            print_run(run)
            pos["run"] = run
            await c.call("emulator/run_frames", {"frames": 30})

        await c.close()

    try:
        asyncio.run(body())
    finally:
        inst.reap()
    with open(os.path.join(a.out_dir, "probe.json"), "w") as fh:
        json.dump(report, fh)
    print(f"\nwrote {os.path.join(a.out_dir, 'probe.json')}   ({time.monotonic() - t0:.1f}s wall)")
    print(f"uptime: {subprocess.run(['uptime'], capture_output=True, text=True).stdout.strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
