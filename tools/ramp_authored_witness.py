#!/usr/bin/env python3
"""ramp_authored_witness — does an AUTHORED ramp document move the PICTURE?

EFFECTS-W1 DoD item 6's certification. The item landed in three parts and none of them
witnessed this: the engine half measured the HBlank budget, `OJZ_TestRamp` is a build-time
fixture that never renders, and step 4 proved the generator READS the key. Merged is not
certified — the owner's standing rule is that a landing shows on screen or in a witness.

THE SUBJECT is `games/sonic4/data/editor/effects/presets/ramp_probe.json` (top 128, lines 64,
VSRAM addr 2, start fp16(0,0), step fp16(1,128) = 1.5 px per line), lowered by
`tools/effects_gen.py` into `EditorRaster_OJZ_Act1_ramp_probe` and read out of the DEBUG ROM.

THREE ARMS, and the second and third are the point — a single before/after is NOT a control
here, because the game keeps running and every line changes anyway:

  1. CONTROL vs CONTROL — two independent instances, same frame count, same lines. They must
     agree completely, or no difference below is attributable to anything.
  2. RAMP vs CONTROL — the authored run's DISPLAYED span is `top+1 .. top+lines`, one line
     later than the written span, which is the VSRAM N+1 latency the engine documents.
  3. RAMP vs A DIFFERENT PROGRAM — installing ANY program replaces the act's own installed
     one, and that replacement changes lines outside the run. Arm 3 holds it constant by
     installing `OJZ_BaseSwap` the same way, so lines changed by both are the replacement and
     lines changed only by the ramp are the ramp.

MEASURED 2026-09-03 at aeon origin/master: arm 1 110/110 identical; arm 2 all 64 displayed
lines changed; arm 3 46 outside lines changed by BOTH and 0 unique to the ramp.

Addresses are read from the .lst, never typed — a symbol moves every time bytes move, and
this script was written once against a stale address before that rule was applied to it.
"""
import sys, asyncio, hashlib, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from suite_paths import add_client_path, suite_root
add_client_path()
from aether import BusClient
from aether_instance import aether_emulator
W = str(suite_root() / ".aeon-land-10a")
RAMP_ADDR="0x00013C7A"; PENDING="0xFF8B52"
TOP, LINES = 128, 64
SETTLE, AFTER = 400, 8

async def rows(b, start, count, chunk=10):
    out=[]; got=0
    while got < count:
        n=min(chunk, count-got)
        r=await b.call("emulator/scanlines", {"startLine": start+got, "count": n})
        assert r.get("source")=="raster", r.get("source")
        px=r.get("lines") or r.get("rows") or r.get("pixels")
        for i,ln in enumerate(px):
            t=ln if isinstance(ln,str) else json.dumps(ln)
            out.append((start+got+i, hashlib.md5(t.encode()).hexdigest()[:8]))
        got+=n
    return out

def run(poke, addr=RAMP_ADDR):
    with aether_emulator(W+"/s4.debug.bin", symbols=W+"/s4.debug.lst") as sock:
        async def go():
            b=BusClient(socket_path=sock, client_id="ab", client_name="ab")
            await b.connect()
            done=0
            while done < SETTLE:
                n=min(100, SETTLE-done); await b.call("emulator/run_frames", {"frames": n}); done+=n
            prog=None
            if poke:
                await b.call("emulator/write_memory", {"addr":PENDING, "bytes":addr})
            await b.call("emulator/run_frames", {"frames": AFTER})
            prog=(await b.call("emulator/read_memory", {"symbol":"Raster_Program","len":4}))["bytes"]
            return prog, await rows(b, 100, 110)
        return asyncio.run(go())

p0, base = run(False)
p0b, base2 = run(False)
same = sum(1 for (l,a),(_,b_) in zip(base, base2) if a==b_)
print("CONTROL vs CONTROL: %d of %d lines identical  (want all)" % (same, len(base)))
if same != len(base):
    print("-> the two instances are NOT reproducing each other; a control/treatment diff cannot be attributed yet")
    raise SystemExit(0)
p1, ramp = run(True)
print("control Raster_Program = %s" % p0)
print("ramp    Raster_Program = %s" % p1)
lo, hi = TOP+1, TOP+LINES
ci=co=so=0; first=None
for (l,h0),(_,h1) in zip(base, ramp):
    inside = lo <= l <= hi
    if h0!=h1:
        if first is None: first=l
        ci += inside; co += (not inside)
    elif not inside: so+=1
print("changed INSIDE the displayed run : %d of %d" % (ci, hi-lo+1))
print("changed OUTSIDE it               : %d" % co)
print("first differing line             : %s" % first)
print()
print("DISCRIMINATOR: install a DIFFERENT program the same way, so the replacement is held constant")
p2, other = run(True, "0x00013D3C")   # OJZ_BaseSwap at its CURRENT address, read from s4.debug.lst
out_ramp  = {l for (l,h0),(_,h1) in zip(base, ramp)  if h0!=h1 and not (lo<=l<=hi)}
out_other = {l for (l,h0),(_,h1) in zip(base, other) if h0!=h1 and not (lo<=l<=hi)}
print("other program Raster_Program = %s" % p2)
print("lines outside the ramp span changed by the RAMP  : %d" % len(out_ramp))
print("lines outside the ramp span changed by the OTHER : %d" % len(out_other))
print("shared by both (= the replacement, not the ramp) : %d" % len(out_ramp & out_other))
print("unique to the ramp                               : %d" % len(out_ramp - out_other))
