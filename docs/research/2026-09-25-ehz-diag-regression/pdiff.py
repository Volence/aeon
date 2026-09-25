#!/usr/bin/env python3
"""pdiff.py a.json b.json [n]: per-routine inclusive/self cycles per tick, b - a, sorted by |d self|."""
import json, sys
def load(f):
    d = json.load(open(f)); p = d["profile"]; t = max(p["ticks"], 1)
    out = {}
    for r in p["items"]:
        k = r.get("name") or r["addr"]
        o = out.setdefault(k, [0, 0, 0])
        o[0] += r["cyclesTotal"] / t; o[1] += r["cyclesSelfTotal"] / t; o[2] += r["callsTotal"] / t
    for k in ("vint", "hint"):
        b = p["interrupts"][k]
        out["<int " + k + ">"] = [b["cyclesTotal"] / t, b["cyclesSelfTotal"] / t, 0]
    return d["crc"], p["ticks"], p["sampleCycles"] / t, out
ca, ta, sa, A = load(sys.argv[1]); cb, tb, sb, B = load(sys.argv[2])
n = int(sys.argv[3]) if len(sys.argv) > 3 else 30
va = A.get("VSync_Wait", [0])[0]; vb = B.get("VSync_Wait", [0])[0]
print(f"A {ca} ticks {ta} sample/tick {sa:.0f} work/tick {sa - va:.0f}")
print(f"B {cb} ticks {tb} sample/tick {sb:.0f} work/tick {sb - vb:.0f}  d work {sb - vb - sa + va:+.0f}")
keys = set(A) | set(B)
z = [0, 0, 0]
rows = sorted(keys, key=lambda k: -abs(B.get(k, z)[1] - A.get(k, z)[1]))
print(f"{'routine':<44} {'A incl':>8} {'B incl':>8} {'d incl':>8} {'A self':>8} {'B self':>8} {'d self':>8} {'A calls':>7} {'B calls':>7}")
for k in rows[:n]:
    a = A.get(k, z); b = B.get(k, z)
    print(f"{k[:44]:<44} {a[0]:8.0f} {b[0]:8.0f} {b[0]-a[0]:+8.0f} {a[1]:8.0f} {b[1]:8.0f} {b[1]-a[1]:+8.0f} {a[2]:7.2f} {b[2]:7.2f}")
