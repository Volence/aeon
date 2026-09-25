#!/usr/bin/env python3
"""clip_bg_scroll_witness — the BUILT clip ROM's own Hscroll_Buffer, against Sonic 2's.

S2CLIP-ORIGINAL-BGS parcel B-2. `tools/clip_bg_scroll.py` derives each zone's scroll from
s2.asm and `tools/test_clip_bg_scroll.py` holds the derivation and the engine MODEL to Sonic 2's
own routine. Neither boots the ROM. This does: a headless oracle process runs the DEBUG clip ROM,
the camera is placed by hand (Debug_Scene_Freeze pins Camera_Update so a written Camera_X/Y
stays), the frame loop runs the real crossing (Parallax_CheckBoundary -> the zone's preset ->
its parallax config) and the real walker, and the 224-line buffer the VDP would read is
compared, word for word, against:

  1. the ENGINE MODEL (`clip_bg_scroll.engine_bg_words`) at the camera, vscroll and deform
     phase read back from RAM — EXACT equality on every line, both planes' words. This is what
     proves the lowered records the ROM carries are the ones the model describes.
  2. for Emerald Hill, SONIC 2 ITSELF (`run_swscrl_ehz`, s2.asm executed) — reported per band
     as the worst difference on lines where S2 writes a new value and on lines where S2 holds
     one (the ramp's pairs and triples). Reported, not graded: the grade is (1) plus the
     derivation tests, which bound these same differences.

It also checks the installed pointer: Parallax_Current_Config must be the zone's own
OJZ_Clip_Parallax_<key> (from the listing), and the config lerp must have finished.

RUNNER: manual (it boots an emulator, so it cannot live in build.sh — the effects-gates
ruling's reason). Run after `S2CLIP=s2_ehz_cpz DEBUG=1 ./build.sh`:
    python3 tools/clip_bg_scroll_witness.py --rom s4.s2clip.debug.bin --lst s4.s2clip.debug.lst
Exit 0 all probes exact, 1 a mismatch, 2 could not measure (symbols missing, a probe that never
settled, a config pointer that is not a clip parallax record).
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from suite_paths import add_client_path, harness_path  # noqa: E402
add_client_path()
sys.path.insert(0, str(harness_path()))
from aether import BusClient            # noqa: E402
from launcher import headless_emulator   # noqa: E402
from raster_cost_probe import parse_lst  # noqa: E402
import clip_bg_scroll as CBS             # noqa: E402
import clip_manifest as CM               # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SYMS = ["Hscroll_Buffer", "Camera_X", "Camera_Y", "Debug_Scene_Freeze",
        "Parallax_Current_Config", "Parallax_Current_Vscroll_BG", "Parallax_Transition_Frames",
        "Parallax_Deform_Phase_BG"]
HSCROLL_BYTES = CBS.SCREEN_LINES * 4
SETTLE_MAX = 900
STABLE_FRAMES = 30


def probes(act):
    """Camera positions per zone: its own x span (camera left edge, clamped so the CENTRE is
    inside the zone's clip) at a few heights inside its paste. Derived from the manifest."""
    out = []
    half_w, half_h = 160, 112
    for c in act.clips:
        x0, y0, w, h = c.dst
        xs = sorted({x0 + 64, x0 + w // 3 + 37, x0 + (2 * w) // 3 + 5, x0 + w - 2 * half_w - 3})
        ys = sorted({y0, y0 + h // 3 + 11, y0 + h - 2 * half_h})
        for x in xs:
            for y in ys:
                out.append((c.zone_key, c.zone, c.dst[1] - c.src[1], max(0, x), max(0, y)))
    return out


async def _probe(b, sym, camx, camy):
    await b.call("emulator/write_memory", {"addr": hex(sym["Camera_X"]), "value": camx << 16,
                                           "width": 4})
    await b.call("emulator/write_memory", {"addr": hex(sym["Camera_Y"]), "value": camy << 16,
                                           "width": 4})
    # SETTLED means all three, for STABLE_FRAMES frames running: no config lerp in flight, the
    # BG vertical scroll no longer moving (Step 5's rate clamp walks it a few px per logic
    # tick, and a camera jump makes lag frames, so "unchanged for 3 frames" was measured to be
    # too short: it sampled vscroll mid-walk), and the buffer's first FG word equal to -camX
    # (a buffer built for the camera just written, not the previous probe's).
    last, stable = None, 0
    want_fg = (-camx) & 0xFFFF
    for n in range(SETTLE_MAX):
        await b.call("emulator/run_frames", {"frames": 1})
        tf = await b.call("emulator/read_memory",
                          {"addr": hex(sym["Parallax_Transition_Frames"]), "len": 1})
        vs = await b.call("emulator/read_memory",
                          {"addr": hex(sym["Parallax_Current_Vscroll_BG"]), "len": 2})
        fg = await b.call("emulator/read_memory",
                          {"addr": hex(sym["Hscroll_Buffer"]), "len": 2})
        cur = (tf["bytes"], vs["bytes"])
        ok = int(tf["bytes"], 16) == 0 and int(fg["bytes"], 16) == want_fg
        stable = stable + 1 if cur == last and ok else 0
        last = cur
        if stable >= STABLE_FRAMES:
            break
    else:
        return None
    rd = {}
    for name, ln in (("Hscroll_Buffer", HSCROLL_BYTES), ("Camera_X", 4), ("Camera_Y", 4),
                     ("Parallax_Current_Config", 4), ("Parallax_Current_Vscroll_BG", 2),
                     ("Parallax_Deform_Phase_BG", 2)):
        r = await b.call("emulator/read_memory", {"addr": hex(sym[name]), "len": ln})
        rd[name] = bytes.fromhex(r["bytes"])
    return rd, n + 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rom", default="s4.s2clip.debug.bin")
    ap.add_argument("--lst", default="s4.s2clip.debug.lst")
    ap.add_argument("--clip", default="s2_ehz_cpz")
    ap.add_argument("--settle", type=int, default=180)
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    rom, lst = str(Path(a.rom).resolve()), str(Path(a.lst).resolve())
    sym = parse_lst(lst)
    act = CM.load(str(REPO / "games" / "sonic4" / "data" / "clips" / a.clip / "clips.json"))
    zones = {c.zone_key: c for c in act.clips}
    need = SYMS + [CBS.PARALLAX_LABEL.format(key=k) for k in zones]
    missing = [s for s in need if s not in sym]
    if missing:
        print(f"COULD NOT RUN: symbols missing from {a.lst}: {', '.join(missing)}")
        return 2
    with open(CBS.s2_asm_path(zones[min(zones)].donor), errors="replace") as fh:
        text = fh.read()
    specs = {k: CBS.derive(c.donor, c.zone, c.dst[1] - c.src[1]) for k, c in zones.items()}
    cfg_of = {sym[CBS.PARALLAX_LABEL.format(key=k)] & 0xFFFFFF: k for k in zones}
    plan = probes(act)
    results = []

    async def run(sock):
        b = BusClient(socket_path=sock, client_id="clipscroll", client_name="clip_bg_scroll_witness")
        await b.connect()
        await b.call("emulator/load_symbols", {"path": lst})
        # `run` only: the legacy server's OpReset reads nothing else and always blocks on the
        # drain (tools/test_legacy_seam_keys.py's reset.wait row says why `wait` is not sent).
        await b.call("emulator/reset", {"run": False})
        await b.call("emulator/run_frames", {"frames": a.settle})
        await b.call("emulator/write_memory", {"addr": hex(sym["Debug_Scene_Freeze"]),
                                               "value": 1, "width": 1})
        await b.call("emulator/run_frames", {"frames": 2})
        for key, zone, dy, x, y in plan:
            results.append((key, zone, x, y, await _probe(b, sym, x, y)))
        await b.close()

    with headless_emulator(rom) as sock:
        asyncio.run(run(sock))

    bad, unmeasured, report = 0, 0, []
    for key, zone, x, y, got in results:
        if got is None:
            print(f"COULD NOT MEASURE {zone} cam ({x},{y}): never settled in {SETTLE_MAX} frames")
            unmeasured += 1
            continue
        rd, frames = got
        camx = int.from_bytes(rd["Camera_X"][:2], "big")
        camy = int.from_bytes(rd["Camera_Y"][:2], "big")
        cfg = int.from_bytes(rd["Parallax_Current_Config"], "big") & 0xFFFFFF
        vs = CBS._sx(int.from_bytes(rd["Parallax_Current_Vscroll_BG"], "big"), 16)
        ph = int.from_bytes(rd["Parallax_Deform_Phase_BG"], "big")
        buf = rd["Hscroll_Buffer"]
        fg = [CBS._sx(int.from_bytes(buf[i * 4:i * 4 + 2], "big"), 16) for i in range(224)]
        bg = [CBS._sx(int.from_bytes(buf[i * 4 + 2:i * 4 + 4], "big"), 16) for i in range(224)]
        line = f"{zone} cam ({camx},{camy}) settled {frames}f vscroll {vs} phase {ph}"
        if (camx, camy) != (x, y):
            print(f"COULD NOT MEASURE {line}: the camera did not stay at ({x},{y})")
            unmeasured += 1
            continue
        if cfg_of.get(cfg) != key:
            print(f"FAIL {line}: Parallax_Current_Config ${cfg:06X} is not "
                  f"{CBS.PARALLAX_LABEL.format(key=key)} (${sym[CBS.PARALLAX_LABEL.format(key=key)] & 0xFFFFFF:06X})")
            bad += 1
            continue
        spec = specs[key]
        want_vs = CBS.engine_vscroll(spec, camy)
        model = CBS.engine_bg_words(spec, camx, vscroll=vs, phase_bg=ph)
        miss = [i for i in range(224) if model[i] != bg[i]]
        fg_miss = [i for i in range(224) if fg[i] != CBS._sx(-camx, 16)]
        ok = not miss and not fg_miss and vs == want_vs
        extra = ""
        if zone == "EHZ" and ok:
            rows, _ = CBS.run_swscrl_ehz(text, camx)
            per = {}
            for k_, b_ in enumerate(spec["bands"]):
                st = set(CBS.group_starts(b_)) if b_["kind"] == "ramp" else None
                for i in range(b_["plane_top"], b_.get("engine_end") or 224):
                    if rows[i] is None:
                        continue
                    d = abs(CBS._sx(bg[i] - CBS._sx(rows[i][1], 16), 16))
                    slot = 0 if st is None or i in st else 1
                    per.setdefault(k_, [0, 0])[slot] = max(per.setdefault(k_, [0, 0])[slot], d)
            extra = f"  vs Sonic 2 (new-value, held) px per band: {per}"
        print(("OK   " if ok else "FAIL ") + line
              + ("" if ok else f"  BG lines differing from the model: {miss[:12]}"
                 f"{'...' if len(miss) > 12 else ''} ({len(miss)}), FG {len(fg_miss)}, "
                 f"vscroll want {want_vs}") + extra)
        bad += 0 if ok else 1
        report.append({"zone": zone, "cam": [camx, camy], "vscroll": vs, "phase": ph,
                       "ok": ok, "bg_miss": len(miss)})
    total = len(results)
    print(f"clip_bg_scroll_witness: {total} probe(s), {total - bad - unmeasured} exact, "
          f"{bad} FAIL, {unmeasured} could not measure  (rom {os.path.basename(rom)})")
    if a.json:
        Path(a.json).write_text(json.dumps(report, indent=1))
    return 2 if unmeasured else (1 if bad else 0)


if __name__ == "__main__":
    sys.exit(main())
