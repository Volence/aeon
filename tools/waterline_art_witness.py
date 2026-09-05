#!/usr/bin/env python3
"""waterline_art_witness — do the row-gathered waterline strips actually reach VRAM?

EFFECTS-W1 item 9d, and the twin of tools/row_remap_witness.py. That one asks whether the
SCROLL half reaches Hscroll_Buffer; this asks whether the ART half reaches the fixed VRAM run
`waterline_strips` — and, unlike the scroll half, this one has an object of its own to look
at: 256 bytes at $B200 that nothing else in the engine writes.

WHY IT STILL IS NOT "READ VRAM AND SEE IF IT CHANGED". Two reasons, and the second is the
one that matters. A changing buffer only says something ran; it does not say the GATHER ran,
on the ladder row the perspective quantity selected, out of the source image the ROM carries.
And the guard means the strips DO NOT change on most frames by design — a witness that
demanded change would fail hardest when the effect was working correctly and the camera was
still.

So the prediction is exact and derived, in three steps that touch nothing of the subject:

  1. Read `Waterline_Art_Row` out of RAM. That is the longword the row-remap pass published
     this frame — `&ladder[H - |p|][0]`. It is a ROM ADDRESS, so the ladder row index falls
     out of it: (row_ptr - RowRemapLadder) / H.
  2. Read the H ladder bytes at that address OUT OF THE ROM IMAGE ON DISK, and the source
     strips out of the same image. Nothing is fitted and nothing comes from the emulator
     except the row pointer.
  3. Compute `waterline_art_gen.gather(H, source, ladder_row)` — the same transpose the
     68000 runs, spelled independently — and compare it to a VRAM read at
     VRAM_WATERLINE_STRIPS, byte for byte.

THREE VERDICTS, AND ALL THREE ARE REQUIRED. The first two are the pair row_remap_witness
learned to demand; the third is this effect's own.

  1. POSITIVE — VRAM equals the prediction for the published row. The gather ran, on that
     row, out of that image, and the DMA landed at that address.
  2. CONTROL — VRAM does NOT equal the prediction for the IDENTITY row (ladder row H, the
     uncompressed surface). Without this arm a gather that ignored the ladder entirely and
     copied rows 0..H-1 straight through would satisfy verdict 1 whenever |p| happened to be
     small, and "the strips are in VRAM" would be reported as "the remap works". If the
     control cannot separate, the run says so instead of passing: at |p| = 0 and |p| = 1 the
     ladder model IS the identity (its `extra` term floors to zero), so those samples are
     reported as UNSEPARATED rather than counted either way.
  3. GUARD — across the sampled frames, the strips change when `Waterline_Art_Row` changes
     and DO NOT change when it does not. That is S3K's `cmp.w (a3),d1 / beq` (:53984)
     observed rather than assumed, and it is the arm that would catch a gather rebuilt every
     frame (correct picture, wasted ~2,240 cycles) or a commit that never happens (correct
     first frame, frozen after).

RUN, AND THE RESULT (2026-09-04, s4.debug.bin 845,147 B, 12 samples at stride 10):

    POSITIVE  12/12 frames — VRAM equals the gather predicted from the published row
    CONTROL   12/12 separable frames differ from the identity gather (0 unseparated)
    GUARD     11 consistent / 0 inconsistent — 2 REBUILT on a row change, 9 SKIPPED
    VERDICT PASS, exit 0

The run settles from ladder row 5 through 3 to 1 (|p| 11 -> 13 -> 15, clamped at H-1) over
the first three samples and then stops, because the camera stops. That is what populates
BOTH sides of the guard arm — 2 transitions where the row moved and the strips were rebuilt,
9 where it did not and they were not — and it is why the two are counted separately below
rather than as one "consistent" total. A single total would pass trivially on a run where the
row never moved: every transition would be (unchanged, unchanged) and nothing would ever have
tested the rebuild.

HOW TO RUN IT (the scene has to be installed the way row_remap_witness installs it — the
shipped section does NOT install ParallaxConfig_OJZ_Underwater, so the remapping band is
reached through the same hand install):

    DEBUG=1 ./build.sh                      # s4.debug.bin + s4.debug.lst
    python3 tools/waterline_art_witness.py  # defaults to s4.debug.bin

WHAT IT STILL DOES NOT SHOW: a picture. These 8 tiles are in VRAM and correct, and NO PLANE
CELL POINTS AT THEM — the OJZ background has no water surface to promote (item-9 design
section 6.2), so nothing in the shipped nametable references VRAM_WATERLINE_STRIPS. This
witness is the whole of the on-screen evidence until an authored background places them.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import waterline_art_gen as model                          # noqa: E402
from suite_paths import add_client_path                    # noqa: E402

add_client_path()
from aether import BusClient                               # noqa: E402
from aether_instance import AetherInstance                 # noqa: E402


class Refused(RuntimeError):
    pass


def refuse(msg: str) -> Refused:
    return Refused(msg)


def _hex(s) -> int:
    s = str(s)
    return int(s[2:] if s[:2].lower() == "0x" else (s[1:] if s[:1] == "$" else s), 16)


async def lookup(c: BusClient, name: str) -> int:
    try:
        r = await c.call("emulator/lookup_symbol", {"name": name})
    except Exception as e:
        raise refuse(f"symbol {name!r} does not resolve against the loaded listing: {e}")
    return _hex(r["addr"])


async def rd(c: BusClient, addr: int, length: int) -> int:
    r = await c.call("emulator/read_memory", {"addr": hex(addr), "len": length})
    return _hex(r["bytes"])


async def read_vram(c: BusClient, addr: int, n: int) -> bytes:
    r = await c.call("emulator/read_vram", {"addr": hex(addr), "len": n})
    raw = str(r["bytes"])
    raw = raw[2:] if raw[:2].lower() == "0x" else raw
    got = bytes.fromhex(raw)
    if len(got) != n:
        raise refuse(f"read_vram(${addr:04X}, {n}) returned {len(got)} B")
    return got


async def frame_no(c: BusClient) -> int:
    return int((await c.call("emulator/status", {}))["frame"])


def declared_vram_base(repo: str) -> int:
    """`waterline_strips`' base SLOT out of games/sonic4/vram.toml — the declaration the
    engine constant is cross-checked against, read rather than restated."""
    import tomllib
    p = os.path.join(repo, "games/sonic4/vram.toml")
    with open(p, "rb") as fh:
        doc = tomllib.load(fh)
    for r in doc.get("region", []):
        if r.get("name") == "waterline_strips":
            return int(r["base"])
    raise refuse(f"{p} declares no region 'waterline_strips'")


def dsl_H(repo: str) -> int:
    """WATERLINE_H, resolved through its alias, out of the engine source. Never typed."""
    import re
    p = os.path.join(repo, "engine/level/parallax_dsl.emp")
    text = open(p, encoding="utf-8").read()
    m = re.search(r"^pub const WATERLINE_H\s*=\s*([A-Za-z0-9_]+)", text, re.M)
    if not m:
        raise refuse(f"WATERLINE_H is not declared in {p}")
    tok = m.group(1)
    if tok.isdigit():
        return int(tok)
    m2 = re.search(r"^pub const " + tok + r"\s*=\s*(\d+)", text, re.M)
    if not m2:
        raise refuse(f"WATERLINE_H = {tok}, which is not a literal const in {p}")
    return int(m2.group(1))


async def run(a) -> int:
    rom_path = os.path.abspath(a.rom)
    lst = os.path.abspath(a.lst) if a.lst else rom_path[:-4] + ".lst"
    rom = open(rom_path, "rb").read()
    H = dsl_H(a.repo)
    src_len, dst_len = model.src_bytes(H), model.dst_bytes(H)
    print(f"  H = {H}; source image {src_len} B, DMA {dst_len} B, "
          f"{model.tiles_for_height(H)} tiles")

    inst = AetherInstance(rom=rom_path, symbols=lst)
    sock = await asyncio.to_thread(inst.start)
    out = {"rom": rom_path, "rom_bytes": len(rom), "H": H, "frames": []}
    try:
        c = BusClient(socket_path=sock, client_id="waterlinew",
                      client_name="waterline_art_witness")
        await c.connect()
        st = await c.call("emulator/status", {})
        # ⚠ ROM IDENTITY FIRST, ALWAYS. A stale shim serves a previous freeze behind a
        # correct-looking romPath, and every number below would then describe another build.
        if int(st["romBytes"]) != len(rom):
            raise refuse(f"server serves {st['romBytes']} bytes, {rom_path} is {len(rom)} "
                         f"— a different ROM")
        print(f"  server romPath={st['romPath']} romBytes={st['romBytes']} (matches disk)")
        out["server_rom_path"] = st["romPath"]

        names = ["Waterline_Art_Row", "Waterline_Art_LastRow", "Waterline_Art_Buffer",
                 "WaterlineStripArt", "RowRemapLadder_Waterline16",
                 "Parallax_Current_Config", "Parallax_Target_Config",
                 "Parallax_Transition_Frames"]
        sym = {n: await lookup(c, n) for n in names}
        out["symbols"] = {k: f"${v:06X}" for k, v in sym.items()}

        ladder_at = sym["RowRemapLadder_Waterline16"] & 0xFFFFFF
        art_at = sym["WaterlineStripArt"] & 0xFFFFFF
        source = rom[art_at:art_at + src_len]
        if source != model.image(H):
            raise refuse(
                f"the source image at ${art_at:06X} in {rom_path} is not the model — run "
                f"tools/waterline_art_gate.py first; every prediction below would be built "
                f"on bytes this witness cannot vouch for")
        print(f"  source image ${art_at:06X} matches the model; ladder ${ladder_at:06X}")

        await c.call("emulator/run_frames", {"frames": a.settle})

        # -- install the hand-authored scene, exactly as row_remap_witness does, and for the
        #    same reason: the shipped section installs a generated editor config, not
        #    ParallaxConfig_OJZ_Underwater, so the remapping band is not otherwise reached.
        cfg = await lookup(c, a.config)
        for s in ("Parallax_Current_Config", "Parallax_Target_Config"):
            await c.call("emulator/write_memory",
                         {"addr": hex(sym[s]), "value": cfg, "width": 4})
        await c.call("emulator/write_memory",
                     {"addr": hex(sym["Parallax_Transition_Frames"]), "value": 0, "width": 1})
        await c.call("emulator/run_frames", {"frames": a.install_settle})
        now = await rd(c, sym["Parallax_Current_Config"], 4)
        if now != cfg:
            raise refuse(f"the engine replaced the installed config: wrote ${cfg:06X}, reads "
                         f"${now:06X} — a section crossing or a transition overwrote it")
        print(f"  installed {a.config} = ${cfg:06X}")

        ok_pos = ok_ctrl = unseparated = guard_ok = guard_bad = 0
        rebuilt, skipped = [], []
        prev_row = prev_vram = None
        for _ in range(a.samples):
            row_ptr = await rd(c, sym["Waterline_Art_Row"], 4)
            last_ptr = await rd(c, sym["Waterline_Art_LastRow"], 4)
            vram = await read_vram(c, a.vram, dst_len)
            rec = {"frame": await frame_no(c), "row_ptr": f"${row_ptr:06X}",
                   "last_ptr": f"${last_ptr:06X}"}

            if row_ptr == 0:
                rec["verdict"] = "NO BAND MARKED"
                out["frames"].append(rec)
                raise refuse(
                    "Waterline_Art_Row is 0 — the row-remap pass marked no band, so the art "
                    "half has nothing to gather. Either no band in the active config carries "
                    "a ladder, or CAP_ROW_REMAP is not declared. Nothing below is testable.")

            off = row_ptr - ladder_at
            if off < 0 or off % H or off // H > H:
                rec["verdict"] = "ROW POINTER OUT OF THE LADDER"
                out["frames"].append(rec)
                raise refuse(
                    f"the published row ${row_ptr:06X} is {off} bytes into "
                    f"RowRemapLadder_Waterline16, which is not a whole row of {H} inside an "
                    f"(H+1)xH table — the pass is publishing something that is not a ladder "
                    f"row, and the gather is indexing the ROM through it")
            r = off // H
            rec["ladder_row"] = r
            rec["abs_p"] = H - r
            ladder_row = rom[row_ptr:row_ptr + H]

            predicted = model.gather(H, source, ladder_row)
            identity = model.gather(H, source, rom[ladder_at + H * H: ladder_at + H * H + H])

            hit = vram == predicted
            sep = predicted != identity
            rec["matches_prediction"] = hit
            rec["control_separates"] = sep
            if hit:
                ok_pos += 1
            else:
                first = next((i for i in range(dst_len) if vram[i] != predicted[i]), None)
                rec["first_difference"] = first
                rec["vram_at_first"] = f"${vram[first]:02X}" if first is not None else None
                rec["predicted_at_first"] = f"${predicted[first]:02X}" if first is not None else None
            if not sep:
                unseparated += 1
                rec["control"] = ("UNSEPARATED — ladder row %d is the identity (|p| = %d), so "
                                  "the remapped and unremapped pictures are the same picture"
                                  % (r, H - r))
            elif vram != identity:
                ok_ctrl += 1
            else:
                rec["control"] = "VRAM equals the IDENTITY gather — the ladder is not indexed"

            if prev_row is not None:
                changed_row = row_ptr != prev_row
                changed_vram = vram != prev_vram
                rec["guard"] = {"row_changed": changed_row, "vram_changed": changed_vram}
                # THE TWO POPULATIONS ARE COUNTED SEPARATELY AND BOTH ARE REQUIRED. A guard
                # arm scored as one "consistent" total passes trivially on a run where the
                # row never moved: every transition is (False, False) and the arm never
                # tested the rebuild at all. Splitting them is what makes an unexercised
                # guard visible instead of green.
                if changed_row == changed_vram:
                    guard_ok += 1
                    (rebuilt if changed_row else skipped).append(rec["frame"])
                else:
                    guard_bad += 1
                    rec["guard"]["verdict"] = (
                        "REBUILT WITHOUT A ROW CHANGE — the S3K guard is not holding and the "
                        "gather runs every frame" if changed_vram else
                        "ROW CHANGED AND VRAM DID NOT — the commit or the DMA is not landing")
            prev_row, prev_vram = row_ptr, vram
            out["frames"].append(rec)
            await c.call("emulator/run_frames", {"frames": a.stride})

        n = a.samples
        out["totals"] = {"samples": n, "positive": ok_pos, "control": ok_ctrl,
                         "unseparated": unseparated,
                         "guard_consistent": guard_ok, "guard_inconsistent": guard_bad,
                         "guard_rebuilt_on_change": rebuilt,
                         "guard_skipped_on_no_change": skipped}
        print(f"  POSITIVE  {ok_pos}/{n} frames: VRAM equals the gather predicted from the "
              f"published ladder row")
        print(f"  CONTROL   {ok_ctrl}/{n - unseparated} separable frames differ from the "
              f"identity gather ({unseparated} unseparated: |p| <= 1 IS the identity)")
        print(f"  GUARD     {guard_ok} consistent / {guard_bad} inconsistent transitions "
              f"— {len(rebuilt)} REBUILT on a row change, {len(skipped)} SKIPPED without one")
        if not rebuilt or not skipped:
            print("  ⚠ THE GUARD ARM IS UNPOPULATED ON ONE SIDE" +
                  (" (no sampled transition changed the row, so nothing tested the rebuild)"
                   if not rebuilt else
                   " (every sampled transition changed the row, so nothing tested the skip)") +
                  " — its consistency total says nothing. Widen --stride or move the camera.")
        verdict = (ok_pos == n and guard_bad == 0 and rebuilt and skipped
                   and ok_ctrl == (n - unseparated) and unseparated < n)
        out["verdict"] = "PASS" if verdict else "FAIL"
        if unseparated == n:
            out["verdict"] = "INCONCLUSIVE"
            print("  ⚠ EVERY sample was at |p| <= 1, where the ladder IS the identity. The "
                  "positive arm cannot distinguish a working gather from a straight copy "
                  "here. Move the camera further from the surface, or raise --samples/--stride.")
        print(f"  VERDICT {out['verdict']}")
        json.dump(out, open(a.out, "w"), indent=1)
        print(f"  wrote {a.out}")
        return 0 if out["verdict"] == "PASS" else 1
    finally:
        await asyncio.to_thread(inst.reap)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default=os.path.join(REPO, "s4.debug.bin"))
    ap.add_argument("--lst", default=None)
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--config", default="ParallaxConfig_OJZ_Underwater",
                    help="the scene whose layer 1 carries the rowRemap")
    ap.add_argument("--vram", type=lambda s: int(s, 0), default=None,
                    help="VRAM byte address of the strips; default is DERIVED from "
                         "games/sonic4/vram.toml's waterline_strips base")
    ap.add_argument("--settle", type=int, default=240)
    ap.add_argument("--install-settle", type=int, default=30)
    ap.add_argument("--samples", type=int, default=12)
    ap.add_argument("--stride", type=int, default=10, help="frames between samples")
    ap.add_argument("--out", default=os.path.join(REPO, "waterline_art_witness.json"))
    a = ap.parse_args()
    if a.vram is None:
        # DERIVED, not defaulted to a literal. A witness carrying its own copy of an address
        # the subject also carries can disagree with the map and still print a verdict — the
        # `--dsb` lesson from tools/row_remap_witness.py, applied before it could bite here.
        a.vram = declared_vram_base(a.repo) * 32
        print(f"  strips at ${a.vram:04X}, derived from games/sonic4/vram.toml")
    try:
        return asyncio.run(run(a))
    except Refused as e:
        print(f"REFUSED: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
