#!/usr/bin/env python3
"""band_witness — do the authored palette bands actually reach the SCREEN?

The claim is NOT "the program builds" (P2a proved that) and NOT "the emitted schedule
carries the right arms" (PIN 5 proves that at build time, statically). It is that the
VDP's palette entry genuinely holds a different colour while the beam is inside each
authored band, and the base colour between them.

INSTRUMENT: CRAM entry $4A (palette line 2, index 5) sampled at chosen scanlines via
`run_to_scanline` + `read_cram` on the Rust core.

VACUITY CHECK, and it is mandatory: if the three in-band probes read the SAME value the
CRAM instrument is frame-latched — it would be reporting end-of-frame state, which is
structurally blind to a mid-frame write, and a matching value would then mean nothing.
The gate refuses in that case rather than passing.

TWO THINGS THIS DOES NOT ESTABLISH, stated because the boundary is where a raster effect
actually fails:
  * `run_to_scanline` is POLLING-based and its own docs say the pause "can land a line or
    two past target". So this confirms the bands EXIST with the right colours in the right
    regions; it does NOT pin the exact transition line. The build-time arm-chain decode
    (PIN 5) is what pins those, and the two are complementary rather than redundant.
  * It samples one CRAM entry. A band that also corrupted a neighbouring entry would pass.

WHY NOT AN A/B AGAINST A BASELINE, measured rather than assumed: installing the band
program REPLACES the act's own raster program, so bands-vs-default differs on every row;
and bands-vs-Raster_Program_None differs on every row too, because removing the act's
per-line work changes the picture by itself. Both moved 122 of 124 rows. Neither isolates
the band. A colour-uniqueness test over pixels also fails, because the bands are coloured
from the act's OWN ground ramp (deliberately, so they read as staged light) and those
colours therefore already appear elsewhere on screen. The palette entry is the subject;
read it directly.
"""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))  # tools/, for suite_paths
from suite_paths import add_client_path  # noqa: E402
add_client_path()  # the Aether client, resolved from the suite root; loud if absent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aether import BusClient
from aether_instance import aether_emulator
from raster_cost_probe import parse_lst

LINE, ENTRY = 2, 5                      # CRAM byte $4A
BASE = 0x026A
BANDS = [((120, 147), 0x0224), ((156, 183), 0x048C), ((192, 219), 0x06AE)]
SEAMS = [155, 191]

async def run(sock, lst):
    b = BusClient(socket_path=sock, client_id="bandw", client_name="band_witness")
    await b.connect()
    await b.call("emulator/load_symbols", {"path": lst})
    sym = parse_lst(lst)                # yields 24-BIT addresses; the bus refuses 0xFFFF____
    await b.call("emulator/reset", {})
    await b.call("emulator/run_frames", {"frames": 180})
    await b.call("emulator/write_memory", {"addr": hex(sym["Debug_Scene_Freeze"]), "value": 1, "width": 1})
    await b.call("emulator/run_frames", {"frames": 2})
    await b.call("emulator/write_memory",
                 {"addr": hex(sym["Raster_Pending"]), "value": sym["OJZ_BandDemo"], "width": 4})
    await b.call("emulator/run_frames", {"frames": 4})

    prog = await b.call("emulator/read_memory", {"addr": hex(sym["Raster_Program"]), "len": 4})
    installed = int(prog["bytes"], 16)
    fails = []
    if installed != sym["OJZ_BandDemo"]:
        return 1, [f"Raster_Program is {installed:#x}, not OJZ_BandDemo {sym['OJZ_BandDemo']:#x} — nothing installed"]

    async def at(line):
        await b.call("emulator/run_to_scanline", {"line": line})
        c = await b.call("emulator/read_cram", {"line": LINE})
        # the reply's list key is not fixed across versions; take whichever list of
        # per-entry dicts it returns rather than assuming one spelling
        ents = next(v for v in c.values()
                    if isinstance(v, list) and v and isinstance(v[0], dict) and "raw" in v[0])
        return int(ents[ENTRY]["raw"], 16)

    print(f"Raster_Program = {installed:#010x} (OJZ_BandDemo)")
    mids = []
    for (lo, hi), want in BANDS:
        mid = (lo + hi) // 2
        got = await at(mid)
        mids.append(got)
        ok = got == want
        print(f"  band {lo}-{hi}: line {mid} reads ${got:04X}, authored ${want:04X}  {'OK' if ok else 'MISMATCH'}")
        if not ok: fails.append(f"band {lo}-{hi} mid line")
    for s in SEAMS:
        got = await at(s)
        ok = got == BASE
        print(f"  seam line {s}: reads ${got:04X}, base ${BASE:04X}  {'OK — restored' if ok else 'MISMATCH'}")
        if not ok: fails.append(f"seam {s}")

    if len(set(mids)) == 1:
        return 1, ["VACUOUS: all three in-band probes read the same value — the CRAM "
                   "instrument is frame-latched and cannot see a mid-frame write. "
                   "UNMEASURABLE, not green."]
    print(f"\nvacuity check: {len(set(mids))} distinct in-band values — the instrument sees mid-frame CRAM")
    return (1, fails) if fails else (0, [])

def main():
    rom, lst = sys.argv[1], sys.argv[2]
    with aether_emulator(rom) as sock:
        rc, fails = asyncio.run(run(sock, lst))
    print("\nRESULT:", "PASS — three bands render their authored colours, base restored between them"
          if rc == 0 else f"FAIL — {fails}")
    return rc

if __name__ == "__main__":
    sys.exit(main())
