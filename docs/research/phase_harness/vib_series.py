#!/usr/bin/env python3
"""fnum -> cents deviation series per channel from the $A4/$A0 write stream.

Per note: base = first applied fnum after key-on; report peak +deviation,
peak -deviation, and contour class (unipolar-up / unipolar-down / bipolar).
Depth (cents) = max(|dev|) per note, aggregated per channel.

Usage: vib_series.py capture.vgm [--dump ch]
"""
import sys

import numpy as np

import vgmlib as V


def main(path, dump_ch=None):
    hdr, ev = V.parse(path)
    kos = V.keyons(ev)
    print(f"== vib_series: {path}")
    print("(note window = key-on .. key-off/next-on-1.5f; series cut at >120c jump = note change)")
    hdrline = (f"  {'ch':>4} {'notes':>6} {'vib notes':>9} {'med depth c':>11} "
               f"{'med +pk':>8} {'med -pk':>8} contour")
    print(hdrline)
    for ch in range(6):
        fs = V.fnum_stream(ev, ch)
        ons = [t for t, c, on, _ in kos if c == ch and on]
        offs = [t for t, c, on, _ in kos if c == ch and not on]
        offs_a = np.array(offs, dtype=np.float64)
        if not ons or not fs:
            continue
        ftimes = np.array([t for t, _, _ in fs], dtype=np.float64)
        depths, pos_pks, neg_pks = [], [], []
        contours = {"up": 0, "down": 0, "bipolar": 0}
        nvib = 0
        for i, t_on in enumerate(ons):
            t_next = ons[i + 1] if i + 1 < len(ons) else hdr["end_t"]
            t_end = t_next - 1.5 * V.FRAME
            if len(offs_a):
                k = np.searchsorted(offs_a, t_on + V.FRAME)
                if k < len(offs_a) and offs_a[k] < t_end:
                    t_end = offs_a[k]
            j0 = np.searchsorted(ftimes, t_on + V.FRAME // 2, side="right") - 1
            if j0 < 0:
                continue
            bb, bf = fs[j0][1], fs[j0][2]
            devs = []
            j = j0 + 1
            while j < len(fs) and ftimes[j] < t_end:
                d = V.cents(fs[j][1], fs[j][2], bb, bf)
                if abs(d) > 120:
                    break  # note change / slide, not vibrato
                devs.append(d)
                j += 1
            if not devs:
                continue
            devs = np.array(devs)
            pk_pos = float(devs.max())
            pk_neg = float(devs.min())
            depth = max(abs(pk_pos), abs(pk_neg))
            if depth < 1.0:
                continue  # no real modulation on this note
            nvib += 1
            depths.append(depth); pos_pks.append(pk_pos); neg_pks.append(pk_neg)
            if pk_neg > -0.25 * depth:
                contours["up"] += 1
            elif pk_pos < 0.25 * depth:
                contours["down"] += 1
            else:
                contours["bipolar"] += 1
            if dump_ch == ch and nvib <= 3:
                print(f"    note@{t_on/V.RATE:.2f}s base=({bb},{bf}) devs:",
                      " ".join(f"{d:+.1f}" for d in devs[:40]))
        if depths:
            print(f"  FM{ch} {len(ons):>6} {nvib:>9} {np.median(depths):>11.1f} "
                  f"{np.median(pos_pks):>8.1f} {np.median(neg_pks):>8.1f} "
                  f"up={contours['up']} down={contours['down']} bipolar={contours['bipolar']}")
        else:
            print(f"  FM{ch} {len(ons):>6} {0:>9}          no modulation")


if __name__ == "__main__":
    d = None
    if "--dump" in sys.argv:
        d = int(sys.argv[sys.argv.index("--dump") + 1])
    main(sys.argv[1], d)
