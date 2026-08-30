#!/usr/bin/env python3
"""parallax_hscroll_identity — the walker's OUTPUT, byte for byte, across ROMs.

WHY THIS EXISTS. `parallax_cost_probe.py` measures what the walker COSTS. Nothing measured
what it PRODUCES, so a cheaper fill that computed slightly different scroll words would have
passed every lane in the tree: the replay net is pixel-blind, `ab_runner` freezes the scene,
and no golden covers `Hscroll_Buffer`. This probe closes that hole for any parcel that
rewrites the fill: it captures the 896-byte buffer for a fixture matrix on a reference ROM and
re-captures it on the candidate, and the two must be EQUAL. The cost may move; the values may
not.

HOW A FIXTURE IS INSTALLED. Identical to `parallax_cost_probe` and deliberately so -- the same
`build()` builds the config, the same four pokes aim `Parallax_Current_Config` at
`Replay_Record_Buf`, and the same three derived checks (pointer still aimed, fixture bytes
unchanged, replay recorder idle) run every time. A fixture that failed to install would
otherwise "match" trivially, because both ROMs would be filling from the same shipped config.

WHAT MAKES THE MATRIX NON-VACUOUS -- the two coverage witnesses, ASSERTED not assumed.
A fill rewritten around a walking table pointer has exactly two new failure surfaces, and a
matrix that misses either is a gate that cannot fail:

  * THE 256-BYTE WRAP. The curve index is (phase + line) & $FF, so a walking pointer must be
    reset when it runs off the end. The deform phase advances every frame, so sampling MANY
    consecutive frames sweeps the wrap across the screen -- but only if the phase actually
    moves and only if some frame's band really does straddle it. `wrap_frames` counts the
    frames whose sampled run crosses a multiple of 256, read from the live phase registers,
    and the run FAILS if the matrix never produced one.
  * SPANS THAT ARE NOT MULTIPLES OF 8. An unrolled fill needs a remainder tail, and every
    cell-aligned fixture hides a broken one: config band tops are CELL rows, so their screen
    lines are all multiples of 8. Fixture ID8 unlocks `v_factor_bg`, which lets Step 4a's
    vscroll rotation land shadow tops on arbitrary scanlines. `ragged_spans` counts spans with
    span % 8 != 0 across the matrix, read back from `Parallax_Shadow_Bands`, and the run FAILS
    if there were none.

Both witnesses are printed on every run, pass or fail, so a future change that quietly makes
the matrix cell-aligned again is visible rather than silently green.

Usage:
    python3 tools/parallax_hscroll_identity.py --rom s4.debug.bin --lst s4.debug.lst \
        --out ref.json                       # capture a reference
    python3 tools/parallax_hscroll_identity.py --rom s4.debug.bin --lst s4.debug.lst \
        --ref ref.json                       # compare against it (exit 1 on any diff)
"""
import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
from suite_paths import add_client_path, harness_path  # noqa: E402
add_client_path()  # the Aether client, resolved from the suite root; loud if absent
HARNESS = str(harness_path())  # legacy oracle_gui launcher; loud if absent
sys.path.insert(0, HARNESS)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aether import BusClient            # noqa: E402
from launcher import headless_emulator   # noqa: E402
from raster_cost_probe import parse_lst  # noqa: E402
from parallax_cost_probe import (        # noqa: E402
    ANCHOR_NONE, BE_SIZE, CFG_ANCHOR_CH, CFG_BAND_COUNT, CFG_SIZE, CFG_V_FACTOR_BG,
    NO_DEFORM, build,
)

HSCROLL_BYTES = 224 * 4          # the whole buffer: 224 lines x (FG word + BG word)
FRAMES = 24                      # consecutive frames per fixture; the phase sweeps the wrap

SYMS = ("Parallax_Current_Config", "Parallax_Target_Config", "Parallax_Transition_Frames",
        "Debug_Scene_Freeze", "Replay_Record_Buf", "Replay_Record_Idx",
        "DeformTable_OJZ_Calm", "DeformTable_Shimmer", "ParallaxConfig_OJZ_Default",
        "Parallax_Shadow_Bands", "Hscroll_Buffer", "Camera_Y",
        "Parallax_Deform_Phase_FG", "Parallax_Deform_Phase_BG")

# THE CURVES MUST DEFLECT. `parallax_cost_probe` attaches `DeformTable_Zero` because a cost
# probe only needs the sampling path to RUN. An identity probe attaching it would be vacuous
# in the worst way: sampling a table of zeros writes base + 0, which is byte-for-byte what the
# flat path writes, so every sampled fixture would "match" a fill that never sampled at all.
# Measured on the first draft of this file -- seven of nine fixtures shared one digest with
# the all-flat fixture. Two DIFFERENT non-zero curves are used so FG and BG are distinguishable
# from each other as well as from flat, and `--ref` comparison is preceded by a vacuity check
# that every sampled fixture differs from ID1.
CURVE_FG = "DeformTable_OJZ_Calm"    # amplitude 96, period 64
CURVE_BG = "DeformTable_Shimmer"     # amplitude 8,  period 32

# The camera Y each fixture is pinned at, AFTER Debug_Scene_Freeze. 144 is the idle baseline.
# A camera that is not a multiple of 8 is what makes an anchored split land on a ragged
# scanline: L is a world anchor minus the camera, and the filler reads shadow tops in SCREEN
# LINES, so an odd camera gives an odd span. Config band tops are CELL rows and can never do
# it, which is why every cell-aligned fixture hides a broken remainder tail.
CAM_Y_IDLE = 144
CAM_Y_RAGGED = 147


def matrix(base: bytes, fg: int, bg: int) -> dict:
    """One fixture per fill PATH, plus the coverage fixtures.

    The paths are what the filler branches to per band: `.lp_flat`, `.band_fg_only`, `.lp_bg`
    and `.lp_both`. Every one is covered, including the ones this parcel did NOT touch -- an
    unchanged path that silently changed is exactly what an identity gate is for. (ID0 used
    to exercise `Parallax_Fill_PerCell`; that filler was deleted 2026-08-26 and a bare config
    now runs the per-line filler on `.lp_flat`, which ID0 still witnesses.)
    """
    return {
        "ID0": {"what": "no table, no deform — the bare config, per-line `.lp_flat` throughout",
                "cfg": build(base, bands=1)},
        "ID1": {"what": "per-line, all 224 lines flat (`.lp_flat`) — the vacuity reference",
                "cfg": build(base, bands=1, tab_fg=fg)},
        "ID2": {"what": "BG-only sampling, 224 lines, phase advancing (`.lp_bg`)",
                "cfg": build(base, bands=1, tab_bg=bg, dsb=2, speed_bg=3)},
        "ID3": {"what": "FG-only sampling, 224 lines, phase advancing (`.band_fg_only`)",
                "cfg": build(base, bands=1, tab_fg=fg, dsa=3, speed_fg=3)},
        "ID4": {"what": "BOTH channels sampling, different curves, phases advancing at "
                        "different rates (`.lp_both` — UNCHANGED path, so this is a control)",
                "cfg": build(base, bands=1, tab_fg=fg, tab_bg=bg, dsa=3, dsb=1,
                             speed_fg=5, speed_bg=2)},
        "ID5": {"what": "3 bands, only the lowest samples FG — flat and sampled bands mixed",
                "cfg": build(base, bands=3, tab_fg=fg, speed_fg=3,
                             shifts=[(NO_DEFORM, NO_DEFORM), (NO_DEFORM, NO_DEFORM),
                                     (3, NO_DEFORM)])},
        "ID6": {"what": "anchored overlay, 2 bands, FG+BG sampling below an arbitrary split",
                "cfg": build(base, bands=2, tab_fg=fg, tab_bg=bg, anchor=0, dsa=3, dsb=3,
                             speed_fg=3, speed_bg=3)},
        "ID7": {"what": "anchored, sampling turned ON BY the anchor (the shipped "
                        "underwater shape: ROM bands all 15, anchor_dsb = 2)",
                "cfg": build(base, bands=4, tab_bg=bg, anchor=0, dsa=NO_DEFORM, dsb=2,
                             speed_bg=1, shifts=[(NO_DEFORM, NO_DEFORM)] * 4)},
        # ID8/ID9 ARE THE RAGGED-SPAN WITNESSES — same shapes as ID7/ID6 but with the camera
        # off the 8-pixel grid, so the anchored split lands on a scanline that is not a cell
        # edge and the unrolled run has a real remainder to finish.
        "ID8": {"what": "ID7's shipped shape at a RAGGED camera (Y=147) — anchored split on "
                        "a non-cell scanline, so spans are not multiples of 8",
                "cam_y": CAM_Y_RAGGED,
                "cfg": build(base, bands=4, tab_bg=bg, anchor=0, dsa=NO_DEFORM, dsb=2,
                             speed_bg=1, shifts=[(NO_DEFORM, NO_DEFORM)] * 4)},
        "ID9": {"what": "FG+BG sampling at a RAGGED camera (Y=147) — ragged spans through "
                        "both the single-channel and the both-channel loop",
                "cam_y": CAM_Y_RAGGED,
                "cfg": build(base, bands=2, tab_fg=fg, tab_bg=bg, anchor=0, dsa=3, dsb=3,
                             speed_fg=3, speed_bg=3)},
    }


async def _one(b: BusClient, sym: dict[str, int], cfg: bytes, settle: int,
               cam_y: int) -> dict:
    for attempt in range(4):     # `reset: timeout waiting for main-thread drain` is an
        try:                     # instrument flake under load — see parallax_cost_probe's note
            await b.call("emulator/reset", {"wait": True, "run": False})
            break
        except Exception:
            if attempt == 3:
                raise
            await asyncio.sleep(1.5)
    await b.call("emulator/run_frames", {"frames": settle})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Debug_Scene_Freeze"]), "value": 1, "width": 1})
    await b.call("emulator/run_frames", {"frames": 2})
    # Camera_Y is 16.16 with the whole pixels in the HIGH word (the walker reads it as
    # `move.l Camera_Y,d1 / swap d1`). Written AFTER the freeze so nothing drives it back.
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Camera_Y"]), "value": cam_y << 16, "width": 4})
    await b.call("emulator/run_frames", {"frames": 2})

    scratch = sym["Replay_Record_Buf"]
    await b.call("emulator/write_memory", {"addr": hex(scratch), "bytes": cfg.hex().upper()})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Parallax_Transition_Frames"]), "value": 0, "width": 1})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Parallax_Target_Config"]), "value": 0, "width": 4})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Parallax_Current_Config"]), "value": scratch, "width": 4})
    await b.call("emulator/run_frames", {"frames": 3})

    idx0 = await b.call("emulator/read_memory",
                        {"addr": hex(sym["Replay_Record_Idx"]), "len": 2})

    frames, tops_seen, phases = [], [], []
    for _ in range(FRAMES):
        await b.call("emulator/run_frames", {"frames": 1})
        buf = await b.call("emulator/read_memory",
                           {"addr": hex(sym["Hscroll_Buffer"]), "len": HSCROLL_BYTES})
        frames.append(buf["bytes"].upper())
        sh = await b.call("emulator/read_memory",
                          {"addr": hex(sym["Parallax_Shadow_Bands"]), "len": BE_SIZE * 6})
        # FOUR hex chars: `band_top_plane` is a u16 since P3 Task 7. A two-char read returns
        # the always-zero HIGH byte of every shadow top in 0..224 and this list silently
        # becomes [0,0,0,...].
        tops_seen.append([int(sh["bytes"][i * BE_SIZE * 2:i * BE_SIZE * 2 + 4], 16)
                          for i in range(6)])
        ph = await b.call("emulator/read_memory",
                          {"addr": hex(sym["Parallax_Deform_Phase_FG"]), "len": 2})
        pb = await b.call("emulator/read_memory",
                          {"addr": hex(sym["Parallax_Deform_Phase_BG"]), "len": 2})
        phases.append((int(ph["bytes"], 16), int(pb["bytes"], 16)))

    ptr = await b.call("emulator/read_memory",
                       {"addr": hex(sym["Parallax_Current_Config"]), "len": 4})
    back = await b.call("emulator/read_memory", {"addr": hex(scratch), "len": len(cfg)})
    idx1 = await b.call("emulator/read_memory",
                        {"addr": hex(sym["Replay_Record_Idx"]), "len": 2})
    cam = await b.call("emulator/read_memory", {"addr": hex(sym["Camera_Y"]), "len": 4})
    return {"frames": frames, "tops": tops_seen, "phases": phases,
            "cam_y": int(cam["bytes"][:4], 16),
            "ptr_ok": (int(ptr["bytes"][:8], 16) & 0xFFFFFF) == (scratch & 0xFFFFFF),
            "bytes_ok": back["bytes"].upper() == cfg.hex().upper(),
            "replay_idle": idx0["bytes"] == idx1["bytes"] == "0000"}


def spans_of(tops: list[int], nbands: int) -> list[int]:
    """Screen-line spans of the shadow bands, in the order the filler walks them."""
    t = [x for x in tops[:nbands]]
    return [(t[i + 1] if i + 1 < len(t) else 224) - t[i] for i in range(len(t))]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rom", default="s4.debug.bin")
    ap.add_argument("--lst", default="s4.debug.lst")
    ap.add_argument("--settle", type=int, default=180)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--out", default="")
    ap.add_argument("--ref", default="")
    args = ap.parse_args()

    args.rom = str(Path(args.rom).resolve())
    args.lst = str(Path(args.lst).resolve())
    sym = parse_lst(args.lst)
    missing = [s for s in SYMS if s not in sym]
    if missing:
        print(f"symbols missing: {', '.join(missing)}", file=sys.stderr)
        return 3

    rom = Path(args.rom).read_bytes()
    off = sym["ParallaxConfig_OJZ_Default"]
    FX = matrix(rom[off:off + CFG_SIZE], sym[CURVE_FG], sym[CURVE_BG])
    got: dict[str, list[dict]] = {k: [] for k in FX}

    async def _sweep(sock: str) -> None:
        b = BusClient(socket_path=sock, client_id="pxident",
                      client_name="parallax_hscroll_identity")
        await b.connect()
        await b.call("emulator/load_symbols", {"path": args.lst})
        for k, fx in FX.items():
            got[k].append(await _one(b, sym, fx["cfg"], args.settle,
                                     fx.get("cam_y", CAM_Y_IDLE)))
        await b.close()

    for _ in range(args.repeat):
        with headless_emulator(args.rom) as sock:
            asyncio.run(_sweep(sock))

    ref = json.loads(Path(args.ref).read_text()) if args.ref else None
    print(f"ROM {args.rom}   {FRAMES} frames/fixture   repeats {args.repeat}")
    print(f"response = Hscroll_Buffer, all {HSCROLL_BYTES} bytes, after each frame\n")
    hdr = (f"{'FIX':4} {'camY':>4} {'bands':>5} {'spans (screen lines)':<30} {'ragged':>6}"
           f" {'wrapF':>6} {'digest':<12} {'vs ref':>8}")
    print(hdr)
    print("-" * len(hdr))

    out, bad, ragged_total, wrap_total = {}, [], 0, 0
    flat_digest = None
    for k, fx in FX.items():
        runs = got[k]
        nb = fx["cfg"][CFG_BAND_COUNT]
        anchored = fx["cfg"][CFG_ANCHOR_CH] != ANCHOR_NONE
        digests = [hashlib.sha256("".join(r["frames"]).encode()).hexdigest() for r in runs]
        stable = len(set(digests)) == 1
        checks = all(r["ptr_ok"] and r["bytes_ok"] and r["replay_idle"] for r in runs)
        r0 = runs[0]
        nshadow = nb + (1 if anchored else 0)
        sp = spans_of(r0["tops"][-1], nshadow)
        ragged = sum(1 for s in sp if s % 8 != 0 and s > 0)
        # a frame WRAPS if the sampled walk crosses a 256 boundary: index0 + 224 >= 256,
        # i.e. the phase's low byte is past 32. Read from the live phase, not assumed.
        wrapf = sum(1 for (pf, pb) in r0["phases"] if ((pf & 0xFF) + 224) > 256
                    or ((pb & 0xFF) + 224) > 256)
        ragged_total += ragged
        wrap_total += wrapf
        note = ""
        if not checks:
            note = "INSTALL!"
            bad.append(f"{k}: fixture did not install cleanly")
        if not stable:
            note = "UNSTABLE"
            bad.append(f"{k}: not reproducible across {args.repeat} boots")
        cmp_s = "-"
        if ref is not None:
            want = ref.get(k, {}).get("digest")
            if want is None:
                cmp_s = "NO-REF"
                bad.append(f"{k}: absent from the reference")
            elif want == digests[0]:
                cmp_s = "match"
            else:
                cmp_s = "DIFFER"
                nf = next((i for i, f in enumerate(runs[0]["frames"])
                           if f != ref[k]["per_frame"][i]), None) \
                    if "per_frame" in ref.get(k, {}) else None
                bad.append(f"{k}: Hscroll_Buffer DIFFERS from the reference"
                           + (f" (first at frame {nf})" if nf is not None else ""))
        # VACUITY: a sampled fixture whose buffer equals the all-flat fixture's is a fixture
        # whose curve never deflected — it would match any fill, including one that dropped
        # the sampling entirely. ID1 IS the flat reference; ID0 is the other filler.
        if k == "ID1":
            flat_digest = digests[0]
        elif k != "ID0" and flat_digest is not None and digests[0] == flat_digest:
            note = "VACUOUS"
            bad.append(f"{k}: sampled buffer is identical to the flat fixture ID1 — the "
                       f"curve did not deflect, so this fixture tests nothing")
        print(f"{k:4} {r0['cam_y']:>4} {nshadow:>5} {str(sp):<30} {ragged:>6} {wrapf:>6}"
              f" {digests[0][:12]:<12} {cmp_s:>8}  {note}")
        out[k] = {"digest": digests[0], "what": fx["what"], "spans": sp, "cam_y": r0["cam_y"],
                  "ragged": ragged, "wrap_frames": wrapf, "checks_ok": checks,
                  "per_frame": runs[0]["frames"]}

    print(f"\nCOVERAGE WITNESSES — ragged spans {ragged_total}   wrapping frames {wrap_total}")
    if ragged_total == 0:
        bad.append("COVERAGE: no non-multiple-of-8 span in the whole matrix — the remainder "
                   "tail is untested and this gate cannot fail on it")
    if wrap_total == 0:
        bad.append("COVERAGE: no frame's sampled run crossed the 256-byte curve wrap — the "
                   "pointer reset is untested and this gate cannot fail on it")

    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=1))
        print(f"\nwrote {args.out}")
    if bad:
        print("\nFAIL")
        for m in bad:
            print(f"  - {m}")
        return 1
    print("\nOK — every fixture's Hscroll_Buffer is byte-identical to the reference"
          if ref is not None else "\nOK — captured (no reference to compare against)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
