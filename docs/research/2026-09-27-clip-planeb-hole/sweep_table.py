#!/usr/bin/env python3
"""Tabulate a sweep: for every out/<tag>.sweep_*.json, did the player get out of loop 1 to the
LEFT (x < 3990), and on which layer/path was he when he did? Works on both our probe's JSON
(`layer`, 0/1) and s2_drive's (`path`, A/B).

    python3 docs/research/2026-09-27-clip-planeb-hole/sweep_table.py <tag>
"""
import glob
import json
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))
tag = sys.argv[1]
tot = {"exited_A": 0, "exited_B": 0, "stayed": 0}
for p in sorted(glob.glob(os.path.join(here, "out", f"{tag}.sweep_*.json"))):
    d = json.load(open(p))
    rows = [r for r in d["rows"] if "x" in r]
    lay = (lambda r: "AB"[r["layer"] & 1]) if "layer" in rows[0] else (lambda r: r["path"])
    out = next((r for r in rows if r["x"] < 3990), None)
    last = rows[-1]
    if out is None:
        tot["stayed"] += 1
        verdict = f"stayed right of 3990 (end x {last['x']} y {last['y']} layer {lay(last)})"
    else:
        tot["exited_" + lay(out)] += 1
        verdict = f"EXITED LEFT at f{out['f']} x {out['x']} y {out['y']} on layer {lay(out)}"
    print(f"{os.path.basename(p)[:-5]:40s} {verdict}")
print(f"TOTAL {sum(tot.values())} drives: exited left on A {tot['exited_A']}, "
      f"exited left on B {tot['exited_B']}, never exited {tot['stayed']}")
