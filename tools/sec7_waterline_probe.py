#!/usr/bin/env python3
"""sec7_waterline_probe — is section 7's waterline a PALETTE boundary on screen?

Boots each ROM headless (tools/aether_instance.py -> oracle-aether, the Rust core),
warps to Aurora's section-7 coordinates through the WARP MAILBOX (a bare camera poke
faults EntityWindow_Scan.slide), and captures REAL RASTER SCANLINES across the band.

TWO ROMS, and the OLD one is the control rather than a decoration: this parcel's whole
risk is that the subject is not on screen at all, in which case both ROMs render the
same rows and a "clean" result means nothing. The old ROM carries the SHADOW/HIGHLIGHT
form of the same boundary, so it must show a boundary too -- just a LUMINANCE one, not a
HUE one. The discriminator below separates those:

    blue_dom(row)  = pixels with B > R + 40 and B > G + 40   (a HUE step -- palette swap)
    luma(row)      = mean (R+G+B)/3                          (a BRIGHTNESS step -- S/H)

Prediction, written before the run:
  new ROM: blue_dom steps UP at the waterline; old ROM: blue_dom flat, luma steps DOWN.
If BOTH are flat on both measures, the boundary is not on screen and NOTHING here is a
verdict about the palette swap -- that is reported as UNMEASURABLE (exit 2), loudly, not
as a pass.

⚠ THIS IS A PROBE, NOT A GATE, AND NOTHING RUNS IT. It needs TWO ROMs built from two
commits, which no runner in this tree can produce, so it is not wired into build.sh or
tools/effects_gates.py and must not be counted as standing coverage. It is committed so
the measurement below is reproducible rather than a number in a commit message.

    Reproduce (from the aeon worktree, both shapes DEBUG):
      git checkout <parcel>~1 -- games/sonic4/data/effects/ojz_effects.emp \
                                 games/sonic4/data/generated/effects_channel_bands.json
      DEBUG=1 ./build.sh && cp s4.debug.bin /tmp/old.bin && cp s4.debug.lst /tmp/old.lst
      git checkout <parcel>   -- <the same two paths>
      DEBUG=1 ./build.sh
      python3 tools/sec7_waterline_probe.py --old-rom /tmp/old.bin --old-lst /tmp/old.lst \
              --new-rom s4.debug.bin --new-lst s4.debug.lst

RECORDED RUN, 2026-09-05, old = the S/H form (parcel~1), new = the palette form:
  both ROMs: warp acked in 18 frames, Camera_Y 4288, Effects_Screen_L [-, -, 32, 122]
    (channel 2's latched screen line 32 = the anchor 4320 minus Camera_Y -- the world
     anchoring, read back from RAM)
  Pal_Variant_Stage slot 0 line 2, entries 3,4,5:
    old  0202 0224 0224   (Water_Deep: darker brown, and 4 and 5 COLLAPSE to one colour)
    new  0A02 0A24 0A44   (Variant_OJZ_Water: three distinct blues, as modelled)
  rows 3..32 are byte-identical between the two ROMs; the first differing row is 33
    (the latch says 32; the Rust core reads the sparse tier one line later -- banked)
  at rows 32 -> 33:  old luma 13.07 -> 6.04 (x0.46, a SHADOW step, hue unchanged)
                     new luma 13.07 -> 12.54 (x0.96, brightness held) and blue-dominant
                     pixels 0 -> 3, rising to 218 where line-2 ground art is dense
  old ROM: ZERO blue-dominant pixels on all 158 captured rows. new ROM: 112 of the 128
  rows below the boundary carry them, mean 120 px of 320.
"""
import argparse, asyncio, json, os, subprocess, sys, time
from pathlib import Path

AEON = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AEON / "tools"))
from suite_paths import add_client_path, suite_path  # noqa: E402
add_client_path()
from aether import BusClient                          # noqa: E402
from aether_instance import assert_rust_server        # noqa: E402
from raster_cost_probe import parse_lst               # noqa: E402

SERVER = str(suite_path("oracle-next", "target", "release", "oracle-aether"))
SETTLE = 180
WARP_X, WARP_Y = 3000, 4400      # Aurora's section-7 coordinates (the owner's own capture point)
POST_WARP = 30
ROW0, ROWN = 3, 160              # channel 2's authored band, exactly


class Setup(Exception):
    pass


class Server:
    def __init__(self, rom, tag):
        self.rom, self.sock = rom, f"/tmp/aeon_sec7pal_{os.getpid()}_{tag}.sock"
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
        self.client = BusClient(self.sock, client_id="sec7pal", client_name="sec7_waterline_probe")
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


def ub(h):
    return int(h.removeprefix("0x").removeprefix("0X"), 16)


async def rd(b, addr, n):
    return bytes.fromhex((await c(b, "emulator/read_memory",
                                  {"addr": hex(addr), "len": n}))["bytes"]
                         .removeprefix("0x").removeprefix("0X"))


async def rows(b, start, count):
    """Raster rows. `source` MUST be 'raster' -- a post-hoc render cannot see a mid-frame
    CRAM write, which is exactly the subject here (memory: mask-then-render is blind)."""
    out = []
    # 16 rows/call: a 224-row reply is ~430 KB on ONE line and blows asyncio's 64 KiB
    # line cap in the Python bus client (banked instrument fact). 16*320*3*2 = 30720 chars.
    step = 16
    for s in range(start, start + count, step):
        n = min(step, start + count - s)
        r = await c(b, "emulator/scanlines", {"startLine": s, "count": n})
        if r.get("source") != "raster":
            raise Setup(f"emulator/scanlines answered source={r.get('source')!r} "
                        f"(caveat {r.get('caveat')!r}) -- a post-hoc render is BLIND to a "
                        f"mid-frame CRAM write and cannot testify here")
        for row in r["rows"]:
            px = bytes.fromhex(row["rgb"].removeprefix("0x").removeprefix("0X"))
            out.append([(px[i], px[i + 1], px[i + 2]) for i in range(0, len(px), 3)])
    return out


def profile(rs):
    prof = []
    for px in rs:
        blue = sum(1 for (r, g, bb) in px if bb > r + 40 and bb > g + 40)
        luma = sum(r + g + bb for (r, g, bb) in px) / (3 * len(px))
        prof.append((blue, round(luma, 2)))
    return prof


async def one(rom, lst, tag):
    sym = parse_lst(lst)
    for n in ("Warp_Req_X", "Warp_Req_Y", "Warp_Req_Flag", "Camera_Y",
              "Pal_Variant_Stage", "Effects_Screen_L"):
        if n not in sym:
            raise Setup(f"{lst}: symbol {n} absent")
    async with Server(rom, tag) as s:
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
            raise Setup("Warp_Req_Flag never cleared in 120 frames -- not in the level state?")
        await c(b, "emulator/run_frames", {"frames": POST_WARP})
        cam_y = int.from_bytes(await rd(b, sym["Camera_Y"], 4), "big") >> 16
        stage = await rd(b, sym["Pal_Variant_Stage"] + 64, 32)       # slot 0, CRAM line 2
        scr_l = await rd(b, sym["Effects_Screen_L"], 8)              # 4 channels, words
        pr = profile(await rows(b, ROW0, ROWN - ROW0 + 1))
        return {"rom": rom, "ack": ack, "cam_y": cam_y,
                "stage_line2": [int.from_bytes(stage[i:i + 2], "big") for i in range(0, 32, 2)],
                "screen_l": [int.from_bytes(scr_l[i:i + 2], "big", signed=True)
                             for i in range(0, 8, 2)],
                "profile": pr}


def step_at(prof, idx):
    """Largest single-row jump in `idx` (0=blue count, 1=luma), and where."""
    best, at = 0.0, None
    for i in range(1, len(prof)):
        d = prof[i][idx] - prof[i - 1][idx]
        if abs(d) > abs(best):
            best, at = d, ROW0 + i
    return best, at


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-rom", required=True)
    ap.add_argument("--old-lst", required=True)
    ap.add_argument("--new-rom", required=True)
    ap.add_argument("--new-lst", required=True)
    ap.add_argument("--json")
    a = ap.parse_args()
    try:
        old = asyncio.run(one(a.old_rom, a.old_lst, "old"))
        new = asyncio.run(one(a.new_rom, a.new_lst, "new"))
    except Setup as e:
        print(f"sec7_waterline_probe: UNMEASURABLE -- {e}", file=sys.stderr)
        return 2

    if a.json:
        Path(a.json).write_text(json.dumps({"old": old, "new": new}, indent=1))

    print(f"warp target (player px)   x={WARP_X} y={WARP_Y}   band rows {ROW0}..{ROWN}")
    for tag, r in (("OLD (sh:1, entries 4,5,6)", old), ("NEW (sh:0, entries 3,4,5)", new)):
        db, ab = step_at(r["profile"], 0)
        dl, al = step_at(r["profile"], 1)
        print(f"\n{tag}")
        print(f"  rom={r['rom']}")
        print(f"  warp acked in {r['ack']} frames; Camera_Y={r['cam_y']}; "
              f"Effects_Screen_L={r['screen_l']}")
        print(f"  Pal_Variant_Stage slot0 line2 = "
              f"{' '.join('%d:%04X' % (i, w) for i, w in enumerate(r['stage_line2']))}")
        print(f"  biggest HUE step (blue-dominant px):   {db:+.0f} px at row {ab}")
        print(f"  biggest LUMA step (mean brightness):   {dl:+.2f} at row {al}")

    identical = old["profile"] == new["profile"]
    print(f"\nrow profiles identical between the two ROMs: {identical}")
    if identical:
        print("UNMEASURABLE: two ROMs that DIFFER rendered byte-identical rows -- the subject "
              "is not on screen at these coordinates and nothing above is a verdict.",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
