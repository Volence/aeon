#!/usr/bin/env python3
"""Per-hit attack RMS of the DAC drum stream (rendered DAC-only waveform).

Uses the $2A byte stream itself (unsigned 8-bit, 0x80-centered) — a faithful
DAC-only render that isolates drums from the FM/PSG mix. Attack window =
first 30 ms of each hit.

Usage: drum_loud.py capture.vgm [boundary_ms=30]
"""
import sys

import numpy as np

import vgmlib as V


def main(path, boundary_ms=30.0):
    hdr, ev = V.parse(path)
    dw = V.dac_writes(ev)
    print(f"== drum_loud: {path}")
    if len(dw) < 10:
        print("no meaningful DAC traffic"); return
    bursts = V.dac_hits(dw)
    atk_win = 0.030 * V.RATE
    rows = []
    for b in bursts:
        t0 = b[0][0]
        vals = np.array([v for t, v in b if t - t0 <= atk_win], dtype=np.float64)
        vals = (vals - 128.0) / 128.0
        rms = np.sqrt((vals ** 2).mean())
        rows.append((t0 / V.RATE, len(b), V.db(rms)))
    arr = np.array([r[2] for r in rows])
    print(f"hits: {len(rows)}   attack RMS dBFS: median={np.median(arr):.1f} "
          f"mean={arr.mean():.1f} p10={np.percentile(arr,10):.1f} p90={np.percentile(arr,90):.1f}")
    print("first 12 hits (t, writes, attack dBFS):")
    for t0, n, d in rows[:12]:
        print(f"  t={t0:7.2f}s  {n:5d} writes  {d:6.1f} dB")


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 30.0)
