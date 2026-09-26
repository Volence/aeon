#!/usr/bin/env python3
# (stressart-budget SAH-2, 2026-09-26) Paths name the parcel's own cache dir, /home/volence/.cache/aeon-sab; re-point them to re-run.
"""SAH-2: cumulative profile windows [lo, hi) for hi in a range; per-frame deltas by
differencing consecutive windows, base vs fix."""
import json
import sys
from pathlib import Path

D = Path("/home/volence/.cache/aeon-sab/sah2w")
lo, a, b = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
focus = sys.argv[4].split(",") if len(sys.argv) > 4 else []


def load(t, hi):
    h = json.loads((D / f"{t}_c{lo}_{hi}.json").read_text())
    p = h["profile"]
    it = {r.get("name") or r["addr"]: r for r in p["items"]}
    return p, it, h["rows"]


for t in ("base", "fix"):
    print(f"== {t}")
    prev = None
    for hi in range(a, b + 1):
        p, it, rows = load(t, hi)
        vs = it.get("VSync_Wait", {}).get("cyclesTotal", 0)
        work = p["sampleCycles"] - vs
        line = f"  [{lo},{hi}) frames {p['frameCount']} ticks {p['ticks']} sample {p['sampleCycles']} work {work}"
        if prev:
            pp, pit = prev
            pvs = pit.get("VSync_Wait", {}).get("cyclesTotal", 0)
            line += f" | +frame: sample {p['sampleCycles'] - pp['sampleCycles']} work {work - (pp['sampleCycles'] - pvs)}"
            for n in focus:
                c = it.get(n, {}).get("cyclesTotal", 0) - pit.get(n, {}).get("cyclesTotal", 0)
                k = it.get(n, {}).get("callsTotal", 0) - pit.get(n, {}).get("callsTotal", 0)
                if c or k:
                    line += f" {n.split('$')[-1]}={c}/{k}"
        print(line, "last row", rows[-1][:6])
        prev = (p, it)
# whole-window routine deltas at the widest window
pb, ib, _ = load("base", b)
pf, if_, _ = load("fix", b)
d = []
for n in set(ib) | set(if_):
    x = ib.get(n, {}).get("cyclesSelfTotal", 0)
    y = if_.get(n, {}).get("cyclesSelfTotal", 0)
    if x != y:
        d.append((y - x, n, x, y, ib.get(n, {}).get("callsTotal", 0), if_.get(n, {}).get("callsTotal", 0)))
d.sort(key=lambda r: -abs(r[0]))
print(f"self-cycle deltas over [{lo},{b}) (fix - base):")
for r in d[:25]:
    print(f"  {r[1][:44]:<44} {r[0]:>8}  ({r[2]} -> {r[3]}; calls {r[4]} -> {r[5]})")
