#!/usr/bin/env python3
"""band_capture — put the authored colour bands in front of the owner as PIXELS.

`band_witness.py` proves the palette entry holds the authored colour while the beam is
inside each band. That is the right instrument for "does the mechanism work", and it is
not an answer to the owner's "nobody has ever seen one". This produces frames a person
can look at, plus the coverage number that explains why they are hard to see.

WHAT IT EMITS, all from ONE paused frame so nothing is compared across runs:
  before-no-bands.png    the act rendering its own raster program
  after-three-bands.png  the same frame with OJZ_BandDemo installed
  annotated-crop.png     a 4x crop of a column the bands actually land on, with the
                         band extents marked — the picture that makes them legible

THE INSTRUMENT NOTE THAT COST AN HOUR, recorded so the next reader does not repeat it:
`emulator/pixel_attribution` is authoritative for `cramIndex` and NOT for `rgb`. Its rgb
field resolves against end-of-frame CRAM, so for every band pixel it reports the BASE
colour while the framebuffer holds the band colour — measured here, all three bands,
702 pixels, zero exceptions. Read `cramIndex` from attribution and the COLOUR from the
png. A frame-latched palette resolve is exactly the hazard band_witness's own header
warns about for CRAM reads; it applies to this method's rgb too.

AND THE ARITHMETIC TRAP UNDER IT: the core's Genesis->RGB is truncating, not rounding.
$0224 renders (72,36,36), not the (73,36,36) a `round()` produces. Two of three bands
then match ZERO pixels and the natural reading is "the band does not render". Compare
against the core's own output (attribution's rgb on a KNOWN entry) rather than against
a formula you wrote.
"""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, "/home/volence/sonic_hacks/empyrean/clients/python")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aether import BusClient
from aether_instance import aether_emulator
from raster_cost_probe import parse_lst
from PIL import Image, ImageDraw
from collections import Counter

SUBJECT = 37                            # CRAM byte $4A = palette line 2, index 5
BASE = 0x026A
BANDS = [((120, 147), 0x0224), ((156, 183), 0x048C), ((192, 219), 0x06AE)]


async def setup(b, lst):
    await b.call("emulator/load_symbols", {"path": lst})
    sym = parse_lst(lst)
    await b.call("emulator/reset", {})
    await b.call("emulator/run_frames", {"frames": 180})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Debug_Scene_Freeze"]), "value": 1, "width": 1})
    await b.call("emulator/run_frames", {"frames": 2})
    return sym


async def run(sock, lst, outdir):
    b = BusClient(socket_path=sock, client_id="bandc", client_name="band_capture")
    await b.connect()
    sym = await setup(b, lst)

    await b.call("emulator/screenshot", {"path": f"{outdir}/before-no-bands.png"})
    print(f"before: {outdir}/before-no-bands.png — the act's own raster program")

    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Raster_Pending"]), "value": sym["OJZ_BandDemo"], "width": 4})
    await b.call("emulator/run_frames", {"frames": 4})
    prog = await b.call("emulator/read_memory", {"addr": hex(sym["Raster_Program"]), "len": 4})
    installed = int(prog["bytes"], 16)
    if installed != sym["OJZ_BandDemo"]:
        raise SystemExit(f"Raster_Program is {installed:#x}, not OJZ_BandDemo — nothing installed")
    shot = f"{outdir}/after-three-bands.png"
    s = await b.call("emulator/screenshot", {"path": shot})
    print(f"after:  {shot} — OJZ_BandDemo installed at {installed:#010x}, frame {s['frame']}")

    # coverage: which pixels does the band mechanism actually own, this frame?
    per_row, pts = Counter(), []
    for y in range(224):
        for x in range(320):
            r = await b.call("emulator/pixel_attribution", {"x": x, "y": y})
            if r.get("cramIndex") == SUBJECT:
                per_row[y] += 1
                pts.append((x, y))
    return shot, per_row, pts, s["frame"]


def annotate(shot, pts, outdir):
    """Crop the columns the bands land on hardest and blow them up 4x."""
    im = Image.open(shot).convert("RGB")
    cols = Counter(x for x, y in pts if 120 <= y <= 219)
    if not cols:
        return None
    centre = max(range(0, 320 - 64), key=lambda x0: sum(cols[x] for x in range(x0, x0 + 64)))
    box = (centre, 108, centre + 64, 224)
    crop = im.crop(box).resize((64 * 4, 116 * 4), Image.NEAREST)
    d = ImageDraw.Draw(crop)
    for (lo, hi), _ in BANDS:
        for y in (lo, hi):
            yy = (y - 108) * 4
            d.line([(0, yy), (crop.size[0], yy)], fill=(255, 0, 255), width=1)
    out = f"{outdir}/annotated-crop.png"
    crop.save(out)
    print(f"crop:   {out} — x {box[0]}-{box[2]}, rows 108-224 at 4x; magenta lines mark the "
          f"authored band edges")
    return out


def main():
    rom, lst, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
    Path(outdir).mkdir(parents=True, exist_ok=True)
    with aether_emulator(rom) as sock:
        shot, per_row, pts, frame = asyncio.run(run(sock, lst, outdir))
    annotate(shot, pts, outdir)

    im = Image.open(shot).convert("RGB")
    px = im.load()
    total = len(pts)
    print(f"\ncoverage of palette line 2 index 5 (the entry the bands paint), frame {frame}:")
    print(f"  whole screen: {total} px of 71680 ({100*total/71680:.2f}%)")
    for (lo, hi), want in BANDS:
        inb = [(x, y) for x, y in pts if lo <= y <= hi]
        c = Counter(px[x, y] for x, y in inb)
        top, n = c.most_common(1)[0]
        print(f"  band {lo}-{hi} (${want:04X}): {len(inb)} px; {n} render {top}, "
              f"{len(inb)-n} still base")
    return 0


if __name__ == "__main__":
    sys.exit(main())
