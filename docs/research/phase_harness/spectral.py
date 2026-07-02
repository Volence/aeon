#!/usr/bin/env python3
"""Band RMS + spectral centroid A/B on rendered audio.

Usage: spectral.py ref.vgm ours.vgm
"""
import sys

import numpy as np

import vgmlib as V

BANDS = [(0, 200), (200, 800), (800, 2000), (2000, 6000), (6000, 10000), (10000, 22050)]


def analyze(path):
    x, sr = V.render(path)
    # trim dead air
    fr = V.frame_rms_db(x, sr)
    idx = np.where(fr > -70)[0]
    fl = int(sr * 0.0167)
    if len(idx):
        x = x[idx[0] * fl:(idx[-1] + 1) * fl]
    n = len(x)
    win = np.hanning(4096)
    hop = 2048
    spec_acc = np.zeros(2049)
    cnt = 0
    for i in range(0, n - 4096, hop):
        X = np.abs(np.fft.rfft(x[i:i + 4096] * win))
        spec_acc += X ** 2
        cnt += 1
    spec = spec_acc / max(cnt, 1)
    freqs = np.fft.rfftfreq(4096, 1 / sr)
    centroid = float((freqs * spec).sum() / spec.sum())
    out = {}
    for lo, hi in BANDS:
        m = (freqs >= lo) & (freqs < hi)
        out[(lo, hi)] = V.db(float(np.sqrt(spec[m].sum() / max(m.sum(), 1))))
    total = V.db(float(np.sqrt((x ** 2).mean())))
    return out, centroid, total


def main(ref, ours):
    print(f"== spectral: ref={ref} ours={ours}")
    br, cr, tr = analyze(ref)
    bo, co, to = analyze(ours)
    print(f"  {'band':>14} {'ref dB':>8} {'ours dB':>8} {'delta':>7}")
    for band in BANDS:
        print(f"  {band[0]:>5}-{band[1]:<8} {br[band]:>8.1f} {bo[band]:>8.1f} "
              f"{bo[band]-br[band]:>+7.1f}")
    print(f"  overall RMS: ref {tr:.1f} dB  ours {to:.1f} dB  delta {to-tr:+.1f} dB")
    print(f"  spectral centroid: ref {cr:.0f} Hz  ours {co:.0f} Hz  delta {co-cr:+.0f} Hz")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
