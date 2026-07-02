#!/usr/bin/env python3
"""DAC starvation: histogram of $2A inter-write gaps within drum bursts.

Baseline cadence = capture's own median $2A gap (drivers differ: ours ~18.2-18.4kHz,
S3K ~10-13kHz). Reports % of burst airtime lost to gaps > 1.5x median, max gap,
and full-frame (>=16.7ms) freeze count.

Usage: dac_stall.py capture.vgm [boundary_ms=10]
"""
import sys

import numpy as np

import vgmlib as V


def main(path, boundary_ms=10.0):
    hdr, ev = V.parse(path)
    dw = V.dac_writes(ev)
    print(f"== dac_stall: {path}")
    if len(dw) < 10:
        print("no meaningful DAC traffic"); return
    bursts = V.dac_hits(dw)
        # per-burst median = that drum's own cadence (rates differ per drum)
    g_all, hold_full, hold_excess, meds = [], 0.0, 0.0, []
    for b in bursts:
        ts = np.array([t for t, _ in b], dtype=np.float64)
        gg = np.diff(ts)
        med_b = float(np.median(gg))
        meds.append(med_b)
        m = gg > 1.5 * med_b
        hold_full += float(gg[m].sum())
        hold_excess += float((gg[m] - med_b).sum())
        g_all.append(gg)
    g = np.concatenate(g_all)
    med = float(np.median(np.array(meds)))
    total_air = float(g.sum())
    hold_mask = g > 1.5 * np.repeat([m for m in meds], [len(x) for x in g_all])
    maxgap_ms = float(g.max()) / V.RATE * 1000
    frame_holds = int((g >= 0.0167 * V.RATE).sum())

    print(f"bursts: {len(bursts)}   $2A writes: {len(dw)}   in-burst gaps: {len(g)}")
    print(f"median per-burst cadence gap: {med:.2f} samples = {med/V.RATE*1e6:.1f} us "
          f"->  {V.RATE/med:.0f} Hz")
    print(f"gaps > 1.5x own-burst median: {int(hold_mask.sum())} ({100*hold_mask.mean():.1f}% of gaps)")
    print(f"airtime in hold gaps (full):   {hold_full/total_air*100:.1f}% of burst airtime")
    print(f"airtime lost to holds (excess): {hold_excess/total_air*100:.1f}% of burst airtime")
    print(f"max in-burst gap: {maxgap_ms:.1f} ms   full-frame (>=16.7ms) freezes: {frame_holds}")
    # histogram in ms buckets
    edges_ms = [0, 0.06, 0.1, 0.15, 0.25, 0.5, 1, 2, 5, 10, 17, 35, 1e9]
    edges = [e / 1000 * V.RATE for e in edges_ms]
    hist, _ = np.histogram(g, bins=edges)
    print("gap histogram (ms buckets):")
    for k in range(len(hist)):
        hi = f"{edges_ms[k+1]:g}" if edges_ms[k + 1] < 1e8 else "inf"
        print(f"  [{edges_ms[k]:>6g}..{hi:>5}) ms: {hist[k]}")


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 10.0)
