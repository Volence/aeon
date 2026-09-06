#!/usr/bin/env python3
"""curve_desc_probe -- does a DESCENDING parallax curve garble the background, and where?

THE SUBJECT. `docs/lane-status.json` carries CURVE-DESC: "ENGINE DEFECT: descending
parallax curve garbles the BG; mechanism unestablished". Its only record is the body of
commit df3b8810 ("scene(sec7): the curve-free scene -- descending curves were the
garbage"), whose eight-arm bisect ended: "CURVES REMOVED -> CORRECT; upward curve ->
CORRECT. So a DESCENDING parallax curve garbles the background and an ascending one does
not." That commit booked the mechanism as UNESTABLISHED and named its own sign derivation
as a lead that does not close, because the positive-spread path takes correct floor
division already.

WHAT THIS TOOL SEPARATES, and it is the one question the bisect could not answer from
pictures alone: is the garble a VALUE defect (the walker writes Plane-B HScroll words that
are not the authored ramp) or a CONTENT consequence (the walker writes exactly the
authored ramp, and the authored ramp is a shear too steep for a 512-px wrapping plane)?
Those two have opposite owners -- the first is an engine bug, the second is a data ruling
-- and no screenshot distinguishes them.

    value domain  : Hscroll_Buffer, 224 lines x 4 bytes (FG word, BG word), read out of RAM
                    and compared line by line against an expectation DERIVED from the
                    scene's own authored factors plus the live Camera_X. The derivation is
                    `curve_probe.derive_curve_buffer`, which reads nothing the walker wrote
                    -- reading back `bc_step` would be checking the walker against itself.
    pixel domain  : real raster scanlines (`source == "raster"` asserted; a post-hoc render
                    is blind to a mid-frame effect and fails by showing a clean picture),
                    written out as PNGs so the garble can be LOOKED at.

WHY Hscroll_Buffer IS SAFE TO READ ONCE. It is DMA'd whole to VRAM_HSCROLL_TABLE in VBlank
(engine/system/buffers.emp, "the ONE table") and the raster interpreter never touches it
(raster_dsl.emp writes CRAM and VSRAM only). So the table the VDP fetches for every line of
a frame is the table one read returns. The same is NOT true of CRAM or VSRAM here.

THE ARMS ARE BUILT BY THE CALLER, one ROM each, and each arm is named with the scene JSON
it was built from so the expectation comes from the authored data rather than from a
constant typed here.

    python3 tools/curve_desc_probe.py \
        --arm flat=/tmp/a.bin,/tmp/a.lst,/tmp/a.json \
        --arm desc=/tmp/b.bin,/tmp/b.lst,/tmp/b.json \
        --arm asc=/tmp/c.bin,/tmp/c.lst,/tmp/c.json \
        --png-dir /tmp/curvedesc --json /tmp/curvedesc/out.json

Exit 0 = every arm measured. Exit 2 = UNMEASURABLE (setup, or an arm whose scene model
could not be reconciled with its own measured band boundaries). Never a verdict: this is a
witness, and it is not wired into any runner.
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

AEON = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AEON / "tools"))
from suite_paths import add_client_path, suite_path   # noqa: E402
add_client_path()
from aether import BusClient                          # noqa: E402
from aether_instance import assert_rust_server        # noqa: E402
from raster_cost_probe import parse_lst               # noqa: E402
import curve_probe as cp                              # noqa: E402
import parallax_hscroll_probe as php                  # noqa: E402

SERVER = str(suite_path("oracle-next", "target", "release", "oracle-aether"))
SETTLE = 180
WARP_X, WARP_Y = 3000, 4400      # df3b8810's own bisect coordinates, unchanged
POST_WARP = 30
LINES = php.HSCROLL_LINES        # 224

# engine/level/parallax_dsl.emp:25-40, mirrored. Only the names a scene JSON may spell.
FACTORS = {
    "FACTOR_LOCKED": 0x0FF, "FACTOR_0": 0x0FF,
    "FACTOR_1":    (15 << 4) | 0,
    "FACTOR_1_2":  (15 << 4) | 1,
    "FACTOR_1_4":  (15 << 4) | 2,
    "FACTOR_1_8":  (15 << 4) | 3,
    "FACTOR_1_16": (15 << 4) | 4,
    "FACTOR_1_32": (15 << 4) | 5,
    "FACTOR_3_4":  (1 << 8) | (2 << 4) | 0,
    "FACTOR_3_8":  (3 << 4) | 2,
    "FACTOR_3_16": (4 << 4) | 3,
    "FACTOR_5_8":  (3 << 4) | 1,
    "FACTOR_5_16": (4 << 4) | 2,
    "FACTOR_7_8":  (1 << 8) | (3 << 4) | 0,
    "FACTOR_7_16": (1 << 8) | (4 << 4) | 1,
    "FACTOR_15_16": (1 << 8) | (4 << 4) | 0,
}
# The drift guard: these four are the only spellings the sec7 arms use, and the three
# above them are the ones curve_probe's own table pins. If parallax_dsl renumbers, this
# fires here rather than producing a plausible wrong ramp.
assert FACTORS["FACTOR_1"] == 0x0F0 and FACTORS["FACTOR_1_2"] == 0x0F1
assert FACTORS["FACTOR_1_4"] == 0x0F2 and FACTORS["FACTOR_1_8"] == 0x0F3


class Setup(Exception):
    pass


class Server:
    def __init__(self, rom, tag):
        self.rom = rom
        self.sock = f"/tmp/aeon_curvedesc_{os.getpid()}_{tag}.sock"
        self.proc = self.client = None

    async def __aenter__(self):
        if os.path.exists(self.sock):
            os.unlink(self.sock)
        self.proc = subprocess.Popen([SERVER, self.rom, "--socket", self.sock, "--no-pace"],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(200):
            if os.path.exists(self.sock):
                break
            time.sleep(0.05)
        else:
            raise Setup(f"oracle-aether never created {self.sock}")
        self.client = BusClient(self.sock, client_id="curvedesc",
                                client_name="curve_desc_probe")
        assert_rust_server(await self.client.connect())
        for m in ("emulator/scanlines", "emulator/write_memory", "emulator/read_memory"):
            if not self.client.supports(m):
                raise Setup(f"server does not advertise `{m}`")
        return self

    async def __aexit__(self, *e):
        try:
            if self.client:
                await self.client.close()
        finally:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()


async def c(b, m, p=None, t=180.0):
    return await asyncio.wait_for(b.call(m, p or {}), timeout=t)


async def rd(b, addr, n):
    """Bytes at `addr`. `read_memory` answers hex WITH a 0x prefix; strip it BEFORE any
    positional slicing or every field is two characters off (banked instrument fact)."""
    r = await c(b, "emulator/read_memory", {"addr": hex(addr), "len": n})
    return bytes.fromhex(r["bytes"].removeprefix("0x").removeprefix("0X"))


async def rows(b, start, count):
    out, step = [], 16      # 224 rows on one line blows asyncio's 64 KiB line cap
    for s in range(start, start + count, step):
        n = min(step, start + count - s)
        r = await c(b, "emulator/scanlines", {"startLine": s, "count": n})
        if r.get("source") != "raster":
            raise Setup(f"emulator/scanlines answered source={r.get('source')!r} "
                        f"(caveat {r.get('caveat')!r}) -- a post-hoc render cannot "
                        f"witness a per-line scroll effect")
        for row in r["rows"]:
            px = bytes.fromhex(row["rgb"].removeprefix("0x").removeprefix("0X"))
            out.append([(px[i], px[i + 1], px[i + 2]) for i in range(0, len(px), 3)])
    return out


PLANE_B_SPAN = 512      # engine/level/parallax.emp, mirrored
SCREEN_HEIGHT = 224


def layers_from_scene(path: str):
    """(top_SCREEN_line, fa, fb, curve_to) in SHADOW ORDER, from the AUTHORED JSON.

    TWO HOPS, AND THE SECOND ONE IS WHY THIS FUNCTION IS NOT A ONE-LINER. On a
    vertically LOCKED plane (v_factor 15) `scene_plane_line()` is the IDENTITY -- it
    returns the authored `world_y` and does NOT add v_offset (engine/level/scene_dsl.emp
    :3313-3332). The authored top is therefore a PLANE line. Step 4a then rotates the band
    list every frame against `Vscroll_BG mod 512`, which on a locked plane is pinned at
    v_offset:

        k          = the LAST band whose plane top <= vs           (.find_k)
        band k     is forced to screen line 0                      (the first-entry flag)
        band i > k lands at  plane_top - vs,  +512 if <= 0,  clamped to 224 if > 224

    A scene whose v_offset is 0 -- which is every OTHER locked scene in the tree, per
    scene_vsplit_line's own banner -- has vs == 0, k == 0 and the rotation is the identity,
    which is why "the authored top IS the screen line" reads as a law. It is not one. This
    tool models the rotation because the FIRST scene in the tree with a non-zero v_offset on
    a locked plane is the subject, and modelling it out would have produced a confident
    wrong expectation on every line.

    Every non-locked v_factor is REFUSED rather than modelled: this tool's whole value is
    that its expectation is derived from authored data, not read back off the walker.
    """
    sc = json.loads(Path(path).read_text())
    if sc.get("v_factor") != 15:
        raise Setup(f"{path}: v_factor {sc.get('v_factor')} is not the locked 15; this "
                    f"tool models only the locked plane")
    authored = []
    for ly in sc["layers"]:
        for k in ("fa", "fb"):
            if ly[k] not in FACTORS:
                raise Setup(f"{path}: unknown factor {ly[k]!r}")
        to = None
        if "curve" in ly:
            nm = ly["curve"]["to"]
            if nm not in FACTORS:
                raise Setup(f"{path}: unknown curve factor {nm!r}")
            to = FACTORS[nm]
        authored.append((int(ly["world_y"]), FACTORS[ly["fa"]], FACTORS[ly["fb"]], to))
    authored.sort(key=lambda t: t[0])

    vs = int(sc.get("v_offset", 0)) % PLANE_B_SPAN
    n = len(authored)
    k = 0
    for i in range(1, n):
        if authored[i][0] > vs:
            break
        k = i
    out = []
    for j in range(n):
        i = (k + j) % n
        top = authored[i][0]
        if j == 0:
            screen = 0
        else:
            screen = top - vs
            if screen <= 0:
                screen += PLANE_B_SPAN
            if screen > SCREEN_HEIGHT:
                screen = SCREEN_HEIGHT
        out.append((screen, authored[i][1], authored[i][2], authored[i][3]))
    return out, sc, authored, vs, k


def runs(vals):
    """Adjacent-equal run-length encode: [(first_line, last_line, value), ...]."""
    out = []
    for i, v in enumerate(vals):
        if out and out[-1][2] == v:
            out[-1][1] = i
        else:
            out.append([i, i, v])
    return [tuple(r) for r in out]


async def one(label, rom, lst, scene, png_dir):
    layers, sc, authored, vs_model, k_model = layers_from_scene(scene)
    sym = parse_lst(lst)
    for n in ("Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag", "Camera_X", "Camera_Y",
              "Hscroll_Buffer", "Parallax_Current_Vscroll_BG"):
        if n not in sym:
            raise Setup(f"{lst}: symbol {n} absent")
    async with Server(rom, label) as s:
        b = s.client
        await c(b, "emulator/load_symbols", {"path": lst})
        await c(b, "emulator/reset", {})
        await c(b, "emulator/run_frames", {"frames": SETTLE})
        for a, v, w in ((sym["Warp_Req_X"], WARP_X, 2), (sym["Warp_Req_Y"], WARP_Y, 2),
                        (sym["Warp_Req_Flag"], 1, 1)):
            await c(b, "emulator/write_memory", {"addr": hex(a), "value": v, "width": w})
        ack = None
        for i in range(1, 121):
            await c(b, "emulator/run_frames", {"frames": 1})
            if (await rd(b, sym["Warp_Req_Flag"], 1))[0] == 0:
                ack = i
                break
        if ack is None:
            raise Setup("Warp_Req_Flag never cleared in 120 frames -- not in the level "
                        "state, or the wrong ROM shape")
        await c(b, "emulator/run_frames", {"frames": POST_WARP})

        cam_x = int.from_bytes(await rd(b, sym["Camera_X"], 4), "big") >> 16
        cam_y = int.from_bytes(await rd(b, sym["Camera_Y"], 4), "big") >> 16
        vs_bg = int.from_bytes(await rd(b, sym["Parallax_Current_Vscroll_BG"], 2), "big")
        raw = await rd(b, sym["Hscroll_Buffer"], LINES * 4)
        fg = [php.s16(int.from_bytes(raw[i * 4:i * 4 + 2], "big")) for i in range(LINES)]
        bg = [php.s16(int.from_bytes(raw[i * 4 + 2:i * 4 + 4], "big")) for i in range(LINES)]
        pix = await rows(b, 0, LINES)

    # DROP THE ZERO-LENGTH ENTRIES BEFORE DERIVING. Step 4a's clamp parks every band the
    # rotation pushed off the bottom at screen line 224, and the walker skips them at two
    # `ble`s (the hoist's span test and the fill's entry-length test). Handing them to
    # derive_curve_buffer would divide by a zero span -- which is exactly the state its own
    # assertion refuses, and refusing is right: an empty band has no ramp.
    live = [ly for i, ly in enumerate(layers)
            if (layers[i + 1][0] if i + 1 < len(layers) else LINES) - ly[0] > 0]
    exp = cp.derive_curve_buffer(live, cam_x)
    exp_bg = [php.s16(exp[y][1]) for y in range(LINES)]
    exp_fg = [php.s16(exp[y][0]) for y in range(LINES)]
    d_bg = [bg[y] - exp_bg[y] for y in range(LINES)]
    d_fg = [fg[y] - exp_fg[y] for y in range(LINES)]
    first_bad = next((y for y in range(LINES) if d_bg[y]), None)

    # THE SELF-CONTROL ON THE ROTATION MODEL, and it is the check that caught the model
    # being wrong the first time. `Vscroll_BG` is READ from the machine and must equal the
    # v_offset the rotation was modelled against; if it does not, every derived line below
    # is answering a different question and nothing here is a verdict.
    if vs_model != vs_bg % PLANE_B_SPAN:
        raise Setup(f"{scene}: modelled the rotation against vs={vs_model} (v_offset) but "
                    f"Parallax_Current_Vscroll_BG reads {vs_bg}; the locked-plane "
                    f"assumption does not hold for this ROM")
    # Every band boundary the MODEL predicts on screen must show up in the MEASURED buffer
    # as a discontinuity (a flat layer changes value at its top; a curve layer changes
    # slope). A predicted boundary that is invisible means the model is wrong.
    seen = []
    for (t, _a, _b, _c) in layers[1:]:
        if not (1 <= t < LINES - 1):
            continue
        d_before = bg[t] - bg[t - 1]
        d_after = bg[t + 1] - bg[t]
        seen.append((t, d_before, d_after, d_before != d_after))

    png = None
    if png_dir:
        png = str(Path(png_dir) / f"curve-desc-{label}.png")
        try:
            from PIL import Image
            im = Image.new("RGB", (320, LINES))
            im.putdata([p for row in pix for p in row])
            im.save(png)
        except Exception as e:      # pillow absent: the numbers still stand
            png = f"(not written: {e})"

    return {
        "label": label, "rom": rom, "scene": scene, "ack": ack,
        "cam_x": cam_x, "cam_y": cam_y, "vscroll_bg": vs_bg,
        "v_offset": sc.get("v_offset"), "layers": layers,
        "authored": authored, "rotation_k": k_model,
        "bg": bg, "fg": fg, "exp_bg": exp_bg,
        "bg_runs": runs(bg), "first_bg_mismatch": first_bad,
        "max_abs_bg_delta": max(abs(v) for v in d_bg),
        "max_abs_fg_delta": max(abs(v) for v in d_fg),
        "n_bg_mismatch": sum(1 for v in d_bg if v),
        "boundaries": seen, "png": png,
    }


def report(r):
    print(f"\n=== arm {r['label']} ===")
    print(f"  rom {r['rom']}")
    print(f"  scene {r['scene']}  v_offset={r['v_offset']}")
    print("    authored (PLANE top,fa,fb,to) = "
          + ", ".join("(%d,%03X,%03X,%s)" % (t, a, b, "-" if c_ is None else "%03X" % c_)
                      for (t, a, b, c_) in r["authored"]))
    print(f"    rotated  (SCREEN top,...)     k={r['rotation_k']}  "
          + ", ".join("(%d,%03X,%03X,%s)" % (t, a, b, "-" if c_ is None else "%03X" % c_)
                      for (t, a, b, c_) in r["layers"]))
    print(f"  warp acked in {r['ack']} frames; Camera_X={r['cam_x']} Camera_Y={r['cam_y']}"
          f"  Parallax_Current_Vscroll_BG={r['vscroll_bg']}")
    print(f"  layer-top self-control (line, dBG before, dBG after, discontinuity?):")
    for (t, db, da, ok) in r["boundaries"]:
        print(f"     line {t:4d}   {db:+6d} -> {da:+6d}   {'yes' if ok else 'NO'}")
    print(f"  measured BG runs ({len(r['bg_runs'])} distinct-value runs over 224 lines):")
    for (lo, hi, v) in r["bg_runs"][:8]:
        print(f"     lines {lo:3d}..{hi:3d}  BG={v}")
    if len(r["bg_runs"]) > 8:
        print(f"     ... {len(r['bg_runs']) - 8} more")
    print(f"  BG excursion over the screen: min {min(r['bg'])} max {max(r['bg'])} "
          f"span {max(r['bg']) - min(r['bg'])} px")
    steps = [r["bg"][y] - r["bg"][y - 1] for y in range(1, LINES)]
    print(f"  steepest adjacent BG step: {max(steps, key=abs):+d} px/line")
    print(f"  DERIVED-vs-MEASURED   BG: {r['n_bg_mismatch']} of 224 lines differ, "
          f"max |delta| {r['max_abs_bg_delta']}"
          + ("" if r["first_bg_mismatch"] is None
             else f", first at line {r['first_bg_mismatch']}"))
    print(f"                        FG: max |delta| {r['max_abs_fg_delta']}")
    print(f"  png {r['png']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", action="append", required=True,
                    help="label=rom,lst,scene.json")
    ap.add_argument("--png-dir")
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.png_dir:
        Path(a.png_dir).mkdir(parents=True, exist_ok=True)
    arms = []
    for spec in a.arm:
        label, _, rest = spec.partition("=")
        parts = rest.split(",")
        if len(parts) != 3:
            print(f"curve_desc_probe: --arm wants label=rom,lst,scene.json, got {spec!r}",
                  file=sys.stderr)
            return 2
        arms.append((label, *parts))
    out = []
    try:
        for (label, rom, lst, scene) in arms:
            for p in (rom, lst, scene):
                if not Path(p).is_file():
                    raise Setup(f"missing {p}")
            out.append(asyncio.run(one(label, rom, lst, scene, a.png_dir)))
    except Setup as e:
        print(f"curve_desc_probe: UNMEASURABLE -- {e}", file=sys.stderr)
        return 2
    print(f"curve_desc_probe  warp ({WARP_X},{WARP_Y})  settle {SETTLE}+{POST_WARP}")
    for r in out:
        report(r)
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1))
        print(f"\njson -> {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
