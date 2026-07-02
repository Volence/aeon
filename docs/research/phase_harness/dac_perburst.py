#!/usr/bin/env python3
"""Per-drum-hit wall-clock duration ($2A activity envelope).

Groups bursts by sample count (a proxy for drum identity) and reports
duration stats per class + the overall table.

Usage: dac_perburst.py capture.vgm [boundary_ms=30]
"""
import sys
from collections import defaultdict

import numpy as np

import vgmlib as V


def main(path, boundary_ms=30.0):
    hdr, ev = V.parse(path)
    dw = V.dac_writes(ev)
    print(f"== dac_perburst: {path}")
    if len(dw) < 10:
        print("no meaningful DAC traffic"); return
    bursts = V.dac_hits(dw)
    print(f"bursts (>=32 writes): {len(bursts)}")
    durs = []
    rows = []
    for b in bursts:
        t0, t1 = b[0][0], b[-1][0]
        dur_ms = (t1 - t0) / V.RATE * 1000
        durs.append(dur_ms)
        rows.append((t0 / V.RATE, len(b), dur_ms))
    durs = np.array(durs)
    print(f"duration ms: median={np.median(durs):.1f} mean={durs.mean():.1f} "
          f"p90={np.percentile(durs,90):.1f} max={durs.max():.1f}")

    # class by write count (log2 bucket) so same drum groups together
    classes = defaultdict(list)
    for t0, n, d in rows:
        classes[int(np.log2(n) * 2) / 2].append((n, d))
    print("per size-class (log2 bucket of write count):")
    print(f"  {'~writes':>8} {'hits':>5} {'med ms':>8} {'max ms':>8}")
    for k in sorted(classes):
        arr = classes[k]
        ns = int(np.median([n for n, _ in arr]))
        ds = np.array([d for _, d in arr])
        print(f"  {ns:>8} {len(arr):>5} {np.median(ds):>8.1f} {ds.max():>8.1f}")
    print("first 12 hits (t, writes, ms):")
    for t0, n, d in rows[:12]:
        print(f"  t={t0:7.2f}s  {n:5d} writes  {d:7.1f} ms")


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 30.0)
