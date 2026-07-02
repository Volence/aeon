#!/usr/bin/env python3
"""Rendered A/B: mix bed RMS + digital-silence fraction + per-channel
isolated renders with inter-note silence fraction.

For each FM melody channel we rewrite the VGM keeping only that channel
(vgmlib.write_isolated), render via vgm2wav, and measure:
- channel RMS (dB) over its active span
- inter-note silence fraction: of the frames in the last 25% of each
  note-to-note gap, how many are digitally silent (< -60 dBFS)
Full-mix bed: overall RMS, median frame RMS, % digitally silent frames.

Usage: melody_cmp.py ref.vgm ours.vgm
"""
import sys
import tempfile
from pathlib import Path

import numpy as np

import vgmlib as V

SIL_DB = -60.0


def mix_stats(path, label):
    x, sr = V.render(path)
    fr = V.frame_rms_db(x, sr)
    active = fr[fr > -90]  # trim leading/trailing dead air handled below
    # trim to song span: first/last frame above -70
    idx = np.where(fr > -70)[0]
    fr = fr[idx[0]:idx[-1] + 1] if len(idx) else fr
    rms_all = V.db(np.sqrt((x ** 2).mean()))
    sil = (fr <= SIL_DB).mean() * 100
    print(f"  {label}: bed RMS={rms_all:6.1f} dB  median frame={np.median(fr):6.1f} dB  "
          f"digitally-silent frames={sil:4.1f}%")
    return rms_all, float(np.median(fr)), float(sil)


def chan_stats(path, ch, tdir):
    iso = Path(tdir) / (Path(path).stem + f"_fm{ch}.vgm")
    V.write_isolated(path, iso, keep_fm=ch)
    x, sr = V.render(iso)
    hdr, ev = V.parse(path)
    kos = V.keyons(ev)
    ons = [t for t, c, on, _ in kos if c == ch and on]
    if len(ons) < 4:
        return None
    # channel RMS over active span
    s0 = int(ons[0] / V.RATE * sr)
    s1 = min(len(x), int(hdr["end_t"] / V.RATE * sr))
    seg = x[s0:s1]
    rms = V.db(np.sqrt((seg ** 2).mean())) if len(seg) else float("nan")
    # inter-note tail silence: last 25% of each on->on gap
    fl = int(sr * 0.0167)
    sil_frames = tot_frames = 0
    for i in range(len(ons) - 1):
        a, b = ons[i], ons[i + 1]
        gap = b - a
        t0 = a + 0.75 * gap
        i0, i1 = int(t0 / V.RATE * sr), int(b / V.RATE * sr)
        nfr = (i1 - i0) // fl
        for k in range(nfr):
            w = x[i0 + k * fl:i0 + (k + 1) * fl]
            r = V.db(np.sqrt((w ** 2).mean())) if len(w) else -100
            tot_frames += 1
            if r <= SIL_DB:
                sil_frames += 1
    silpct = 100 * sil_frames / tot_frames if tot_frames else float("nan")
    return len(ons), rms, silpct


def main(ref, ours):
    print(f"== melody_cmp: ref={ref} ours={ours}")
    print("full-mix bed:")
    r = mix_stats(ref, "ref ")
    o = mix_stats(ours, "ours")
    print(f"  delta: bed RMS {o[0]-r[0]:+.1f} dB, median frame {o[1]-r[1]:+.1f} dB, "
          f"silent frames {o[2]-r[2]:+.1f} pp")
    print("per-channel isolated renders (notes / RMS dB / inter-note-tail silence %):")
    with tempfile.TemporaryDirectory() as td:
        for ch in range(6):
            a = chan_stats(ref, ch, td)
            b = chan_stats(ours, ch, td)
            fa = f"{a[0]:4d}n {a[1]:6.1f}dB {a[2]:5.1f}%" if a else "      (inactive)      "
            fb = f"{b[0]:4d}n {b[1]:6.1f}dB {b[2]:5.1f}%" if b else "      (inactive)      "
            print(f"  FM{ch}:  ref {fa}   |   ours {fb}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
