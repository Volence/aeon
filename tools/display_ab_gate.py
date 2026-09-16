#!/usr/bin/env python3
"""DISPLAY-AB — does the machine put the same thing on screen before and after?

THE QUESTION THIS ANSWERS, and it is narrower than "is the ROM the same". A parcel
that re-keys a table, moves a symbol, or re-orders a generated file changes ROM
bytes for reasons that are not a picture change, so a CRC comparison reports a
difference it cannot interpret and a green build reports nothing at all. What a
reader actually wants is: at the same point in the same run, does the VDP hold the
same pixels, the same nametables and the same colours?

So this boots BOTH ROMs headless and reads, at each sample point, everything the
display is made of:

  * the whole 64 KB of VRAM -- tiles, both nametables, the sprite table, the
    HSCROLL table. Whole, not a window: a parcel that moved a plane by one row
    would pass a Plane-B-only comparison that happened to sample the other plane.
  * all 128 bytes of CRAM -- every colour of every palette line.
  * all 80 bytes of VSRAM -- the per-column vertical scroll.

At TWO sample points, because a still frame hides everything that only happens
while the machine is moving:

  * REST   -- boot + `--boot-frames`, nothing held. The first picture.
  * MOTION -- after holding `--hold` for `--hold-frames`. Streaming, region
              crossings, palette fades and raster programs all live here.

⚠ WHAT A GREEN DOES NOT SAY. It does not say the picture is RIGHT: identical-to-
before is the whole assertion, and two identically wrong pictures pass. It also
says nothing about any point in the run this did not sample. Both halves are the
same caveat `tools/bg_nt_gate.py` carries and are repeated rather than cross-
referenced, because a reader reaching a verdict line will not go and look.

NON-VACUITY IS CHECKED, NOT ASSUMED, and every one of these is a REFUSAL (exit 2)
rather than a pass:
  * the MOTION sample must find the camera somewhere the REST sample did not, on
    both sides. A held button that moved nothing leaves this comparing the rest
    picture with itself and calling it two legs.
  * every read must come back the length it was asked for.
  * the two ROMs' CRCs are printed. Comparing a file with itself is a legitimate
    self-test (`--allow-same-rom`) and is REFUSED without that flag, because it is
    also what a mistyped path looks like.

EXIT: 0 identical at every sampled point - 1 a real difference - 2 could not
measure (refusal, spawn failure, missing symbol, vacuous leg).
"""
import argparse
import asyncio
import os
import sys
import zlib
from pathlib import Path

AEON = Path(os.environ.get("AEON_DIR", Path(__file__).resolve().parent.parent)).resolve()
sys.path.insert(0, str(AEON / "tools"))
from suite_paths import add_client_path                           # noqa: E402
add_client_path()
from aether import BusClient                                      # noqa: E402
from aether_instance import (AetherInstance, SpawnError,          # noqa: E402
                             WrongServerError, read_bytes, unprefix)
from raster_cost_probe import parse_lst                           # noqa: E402

VRAM_BYTES = 0x10000
CRAM_BYTES = 128
VSRAM_BYTES = 80
CHUNK = 4096

EXIT_OK, EXIT_DIFF, EXIT_REFUSED = 0, 1, 2

# The VRAM neighbourhoods, for a verdict that names WHERE rather than only how many.
# Read from engine/system/constants.emp so a VRAM re-cut moves this with it rather than
# leaving a report that confidently names the wrong region.
REGION_CONSTS = (("SPRITES", "VRAM_SPRITE_TABLE"),
                 ("HSCROLL", "VRAM_HSCROLL_TABLE"),
                 ("PLANE_A", "VRAM_PLANE_A"),
                 ("PLANE_B", "VRAM_PLANE_B"),
                 ("WINDOW", "VRAM_WINDOW"))


class Refused(RuntimeError):
    pass


def vram_regions() -> list:
    """[(name, start, end)] over the whole 64 KB, derived from the engine's constants.

    Anything not inside a named table is reported as `TILES`, which is what the rest of
    VRAM is. Derived and not typed: a VRAM re-cut that moved a table would otherwise leave
    this report naming the wrong neighbourhood with total confidence, which is worse than
    no name at all."""
    src = (AEON / "engine" / "system" / "constants.emp").read_text()
    named = []
    import re
    for label, const in REGION_CONSTS:
        m = re.search(r"^\s*(?:pub\s+)?const\s+" + re.escape(const) + r"\s*=\s*(\$?[0-9A-Fa-fx]+)",
                      src, re.M)
        if not m:
            raise Refused(f"engine/system/constants.emp declares no `{const}`, so this "
                          f"gate cannot say WHICH part of VRAM differs. Refusing rather "
                          f"than printing a neighbourhood name it guessed.")
        t = m.group(1)
        named.append((label, int(t[1:], 16) if t.startswith("$") else int(t, 0)))
    named.sort(key=lambda p: p[1])
    out, prev_end = [], 0
    # Each named table runs to the next one; the tail after the last is TILES too.
    for i, (label, start) in enumerate(named):
        if start > prev_end:
            out.append(("TILES", prev_end, start))
        end = named[i + 1][1] if i + 1 < len(named) else VRAM_BYTES
        out.append((label, start, end))
        prev_end = end
    if prev_end < VRAM_BYTES:
        out.append(("TILES", prev_end, VRAM_BYTES))
    return out


async def _c(b, method, params=None, timeout=240.0):
    return await asyncio.wait_for(b.call(method, params or {}), timeout=timeout)


async def _block(b, method, addr_key, base, total, label):
    out = bytearray()
    off = 0
    while off < total:
        n = min(CHUNK, total - off)
        r = await _c(b, method, {addr_key: hex(base + off), "len": n})
        h = unprefix(r["bytes"])
        if len(h) != n * 2:
            raise Refused(f"short {label} read at +{off}: {len(h)} hex chars, wanted {n * 2}")
        out += bytes.fromhex(h)
        off += n
    if len(out) != total:
        raise Refused(f"assembled {len(out)} {label} bytes, wanted {total}")
    return bytes(out)


async def read_cram(b) -> bytes:
    """All four palette lines, 16 entries each, as 128 bytes.

    `emulator/read_cram` is LINE-ORIENTED (it answers with a 16-entry list of `raw` words),
    which is why this is not another `_block` call. The shape check is the one
    tools/region_fade_witness.py already makes and is repeated rather than trusted: a short
    line would otherwise silently shorten the comparison instead of failing it."""
    out = bytearray()
    for line in range(4):
        c = await _c(b, "emulator/read_cram", {"line": line})
        ents = next((v for v in c.values()
                     if isinstance(v, list) and v and isinstance(v[0], dict) and "raw" in v[0]),
                    None)
        if ents is None or len(ents) != 16:
            raise Refused(f"read_cram line {line} returned no 16-entry list: {str(c)[:200]}")
        for e in ents:
            out += int(e["raw"], 16).to_bytes(2, "big")
    if len(out) != CRAM_BYTES:
        raise Refused(f"assembled {len(out)} CRAM bytes, wanted {CRAM_BYTES}")
    return bytes(out)


async def read_vsram(b) -> bytes:
    r = await _c(b, "emulator/read", {"space": "vsram", "addr": "0x0", "len": VSRAM_BYTES})
    h = unprefix(r["bytes"])
    if len(h) != VSRAM_BYTES * 2:
        raise Refused(f"short VSRAM read: {len(h)} hex chars, wanted {VSRAM_BYTES * 2}")
    return bytes.fromhex(h)


async def snapshot(b) -> dict:
    """VRAM + CRAM + VSRAM, whole, in one go."""
    return {
        "VRAM": await _block(b, "emulator/read_vram", "addr", 0, VRAM_BYTES, "VRAM"),
        "CRAM": await read_cram(b),
        "VSRAM": await read_vsram(b),
    }


async def rd(b, addr, width):
    return int(await read_bytes(b, addr, width), 16)


async def camera(b, sym):
    return ((await rd(b, sym["Camera_X"], 4)) >> 16,
            (await rd(b, sym["Camera_Y"], 4)) >> 16)


async def capture(rom, lst, a):
    """Both sample points from ONE boot of one ROM."""
    inst = AetherInstance(rom, symbols=lst)
    try:
        sock = await asyncio.to_thread(inst.start)
    except (SpawnError, WrongServerError) as e:
        raise Refused(str(e)) from e
    b = BusClient(sock, client_id="dispab", client_name="display_ab_gate")
    await b.connect()
    try:
        need = ("emulator/read_vram", "emulator/read_cram", "emulator/read",
                "emulator/run_frames", "emulator/read_memory", "emulator/hold",
                "emulator/release_all")
        missing = [m for m in need if not b.supports(m)]
        if missing:
            raise Refused("the server does not advertise " + ", ".join(missing))
        sym = parse_lst(lst)
        for n in ("Camera_X", "Camera_Y"):
            if n not in sym:
                raise Refused(f"{lst} carries no `{n}`, so the motion leg cannot be "
                              f"proven to have moved and would be the rest leg again")

        await _c(b, "emulator/run_frames", {"frames": a.boot_frames})
        rest = await snapshot(b)
        cam_rest = await camera(b, sym)

        # ⚠ THE EXIT-FREE-FLIGHT PRESS, and it is deliberate. A DEBUG build boots into
        # debug free flight, where the held direction moves the player at a constant rate
        # and the ordinary physics never runs — so a motion leg taken in that state is a
        # weaker subject than the one a player produces. `--exit-free-flight` taps B first.
        if a.exit_free_flight:
            await _c(b, "emulator/hold", {"buttons": ["b"], "down": True})
            await _c(b, "emulator/run_frames", {"frames": 2})
            await _c(b, "emulator/hold", {"buttons": ["b"], "down": False})
            await _c(b, "emulator/run_frames", {"frames": 2})

        await _c(b, "emulator/hold", {"buttons": [a.hold], "down": True})
        await _c(b, "emulator/run_frames", {"frames": a.hold_frames})
        await _c(b, "emulator/hold", {"buttons": [a.hold], "down": False})
        await _c(b, "emulator/release_all", {})
        await _c(b, "emulator/run_frames", {"frames": a.settle})
        motion = await snapshot(b)
        cam_motion = await camera(b, sym)

        if cam_rest == cam_motion:
            raise Refused(
                f"{Path(rom).name}: the camera is at {cam_rest!r} at REST and at MOTION — "
                f"holding {a.hold!r} for {a.hold_frames} frames moved nothing, so the "
                f"second sample is the first one again and this run has ONE leg, not two. "
                f"That is a measurement that could not be made, never a pass.")
        print(f"  {Path(rom).name}: camera {cam_rest!r} -> {cam_motion!r} "
              f"across {a.hold_frames} held frames")
        return {"REST": rest, "MOTION": motion}, (cam_rest, cam_motion)
    finally:
        await b.close()
        inst.reap()


def compare(before, after, regions) -> list:
    """[(leg, space, detail)] for every difference. Empty == the display is identical.

    AGGREGATED ACROSS EVERY LEG AND EVERY SPACE — never short-circuited on the first
    mismatch. A gate that stopped at the first difference would report the same thing for a
    tree that moved one palette entry and a tree that moved everything, i.e. it would get no
    louder as the subject got more broken."""
    faults = []
    for leg in ("REST", "MOTION"):
        for space in ("VRAM", "CRAM", "VSRAM"):
            x, y = before[leg][space], after[leg][space]
            if x == y:
                continue
            diff = [i for i in range(len(x)) if x[i] != y[i]]
            if space == "VRAM":
                per = {}
                for i in diff:
                    for name, lo, hi in regions:
                        if lo <= i < hi:
                            per[name] = per.get(name, 0) + 1
                            break
                where = ", ".join(f"{k} {v}" for k, v in sorted(per.items()))
            else:
                where = f"offsets {diff[:16]}{' ...' if len(diff) > 16 else ''}"
            faults.append((leg, space,
                           f"{len(diff)} of {len(x)} byte(s) differ — {where}"))
    return faults


async def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--before-rom", required=True)
    ap.add_argument("--before-lst", required=True)
    ap.add_argument("--after-rom", required=True)
    ap.add_argument("--after-lst", required=True)
    ap.add_argument("--hold", default="right", help="the button held for the MOTION leg")
    ap.add_argument("--boot-frames", type=int, default=120)
    ap.add_argument("--hold-frames", type=int, default=240)
    ap.add_argument("--settle", type=int, default=8)
    ap.add_argument("--exit-free-flight", action="store_true",
                    help="tap B before the motion leg (a DEBUG build boots into debug "
                         "free flight, where ordinary physics never runs)")
    ap.add_argument("--allow-same-rom", action="store_true",
                    help="permit both sides to be the same file — the gate's own control")
    a = ap.parse_args()

    try:
        crcs = {}
        for side, p in (("before", a.before_rom), ("after", a.after_rom)):
            blob = open(p, "rb").read()
            crcs[side] = (len(blob), zlib.crc32(blob) & 0xFFFFFFFF)
            print(f"{side.upper():7} {p}  {len(blob)} bytes  crc32 {crcs[side][1]:08x}")
        if crcs["before"] == crcs["after"] and not a.allow_same_rom:
            raise Refused(
                "both sides are byte-identical ROMs. That is a legitimate SELF-TEST of "
                "this gate and it is also exactly what a mistyped path looks like, so it "
                "needs --allow-same-rom to say which it is. (If the parcel genuinely moved "
                "no bytes, there is nothing for this gate to add: say so with the CRCs.)")
        regions = vram_regions()
        print("VRAM map: " + ", ".join(f"{n} ${lo:04X}-${hi - 1:04X}"
                                       for n, lo, hi in regions))
        before, _ = await capture(a.before_rom, a.before_lst, a)
        after, _ = await capture(a.after_rom, a.after_lst, a)
    except Refused as e:
        print(f"REFUSED: {e}")
        return EXIT_REFUSED
    # ⚠ ANY OTHER EXCEPTION IS ALSO A REFUSAL, AND THIS CLAUSE IS A FIX FOR A DEFECT IN THIS
    # GATE'S OWN FIRST DRAFT. Without it a bus error, a timeout or a bad argument escaped as
    # a traceback and Python exited 1 — this gate's code for "a real difference on screen".
    # A run that could not measure would have been read as a measured change, which is the
    # failure this repo keeps finding in its own gates: the instrument reporting a verdict it
    # did not reach. Found by running the vacuity control (`--hold-frames 0`), which the bus
    # rejects outright, and seeing exit 1 where exit 2 was owed.
    except (Exception, asyncio.CancelledError) as e:  # noqa: BLE001 — see above
        print(f"REFUSED: {type(e).__name__}: {e}")
        return EXIT_REFUSED

    faults = compare(before, after, regions)
    for leg in ("REST", "MOTION"):
        for space in ("VRAM", "CRAM", "VSRAM"):
            hit = [f for f in faults if f[0] == leg and f[1] == space]
            if hit:
                print(f"  {leg:<7} {space:<6} DIFFERS  {hit[0][2]}")
            else:
                print(f"  {leg:<7} {space:<6} IDENTICAL "
                      f"({len(before[leg][space])} bytes)")
    if faults:
        print(f"display_ab_gate: {len(faults)} differing (leg, space) pair(s) — the "
              f"machine does not put the same thing on screen.")
        return EXIT_DIFF
    print("display_ab_gate: OK — whole VRAM, CRAM and VSRAM are byte-identical at REST "
          "and after held input. This says the picture did not change; it does not say "
          "the picture is right, and it says nothing about points in the run it did not "
          "sample.")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
