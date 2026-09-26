#!/usr/bin/env python3
# (stressart-budget SAH-2, 2026-09-26) Paths name the parcel's own cache dir, /home/volence/.cache/aeon-sab; re-point them to re-run.
"""SAH-2: where do the fix's extra lag frames fall, and which routines grew?"""
import json
import sys
from pathlib import Path

D = Path(sys.argv[1])
leg = sys.argv[2] if len(sys.argv) > 2 else "cpzdiag"
b = json.loads((D / f"base_{leg}.json").read_text())
f = json.loads((D / f"fix_{leg}.json").read_text())
k = b["rows_before_switch"]
print("rows_before_switch base", k, "fix", f["rows_before_switch"])


def lagrows(h):
    return [(r[0], r[1] - r[2], r[4], r[5]) for r in h["rows"]]


lb, lf = lagrows(b), lagrows(f)
# lag per 512-px camera-x bucket after the switch, and per camera-y bucket
for name, idx in (("x", 2), ("y", 3)):
    agg = {}
    for tag, rows, kk in (("base", lb, b["rows_before_switch"]), ("fix", lf, f["rows_before_switch"])):
        for r in rows[kk:]:
            bk = r[idx] // 512 * 512
            agg.setdefault(bk, [0, 0])
            agg[bk][0 if tag == "base" else 1] += r[1]
    print(f"lag after switch by camera {name} bucket (base, fix, delta):")
    for bk in sorted(agg):
        a, c = agg[bk]
        if a or c:
            print(f"  {name}={bk:>6}: {a:>3} {c:>3} {c - a:+d}")
# first divergence of camera path
for i, (x, y) in enumerate(zip(lb, lf)):
    if (x[2], x[3]) != (y[2], y[3]) or x[1] != y[1]:
        print("first per-frame divergence at row", i, "base", x, "fix", y)
        break
# lag frame positions listing
print("base lag rows:", [(r[0], r[2], r[3]) for r in lb if r[1] > 0])
print("fix  lag rows:", [(r[0], r[2], r[3]) for r in lf if r[1] > 0])
bp = json.loads((D / f"base_{leg}P.json").read_text()).get("profile")
fp = json.loads((D / f"fix_{leg}P.json").read_text()).get("profile")
if bp and fp:
    print(f"profiled ticks base {bp['ticks']} fix {fp['ticks']}; sampleCycles {bp['sampleCycles']} {fp['sampleCycles']}")
    bi = {r.get("name") or r["addr"]: r for r in bp["items"]}
    fi = {r.get("name") or r["addr"]: r for r in fp["items"]}
    rows = []
    for n in set(bi) | set(fi):
        a = bi.get(n, {}); c = fi.get(n, {})
        rows.append((c.get("cyclesSelfTotal", 0) - a.get("cyclesSelfTotal", 0), n,
                     a.get("cyclesSelfTotal", 0), c.get("cyclesSelfTotal", 0),
                     a.get("callsTotal", 0), c.get("callsTotal", 0),
                     a.get("cyclesTotal", 0), c.get("cyclesTotal", 0)))
    rows.sort(key=lambda r: -abs(r[0]))
    print(f"{'routine':<36} {'dSelf':>9} {'self base':>10} {'self fix':>10} {'calls b':>8} {'calls f':>8} {'incl b':>10} {'incl f':>10}")
    for r in rows[:30]:
        print(f"{r[1][:36]:<36} {r[0]:>9} {r[2]:>10} {r[3]:>10} {r[4]:>8} {r[5]:>8} {r[6]:>10} {r[7]:>10}")
    for n in ("PageCache_DemandHoldTick", "Tile_Cache_Fill", "PageCache_Audit", "PageCache_AllocFrame",
              "PageIn_Process", "PageCache_Publish", "PageCache_Request"):
        a = bi.get(n, {}); c = fi.get(n, {})
        print(f"  {n}: calls {a.get('callsTotal')} -> {c.get('callsTotal')}; incl {a.get('cyclesTotal')} -> {c.get('cyclesTotal')}; self {a.get('cyclesSelfTotal')} -> {c.get('cyclesSelfTotal')}")
