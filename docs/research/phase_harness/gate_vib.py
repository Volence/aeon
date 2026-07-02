#!/usr/bin/env python3
"""Per-note flat-frame count: frames between key-on and the first fnum change.

S3K holds ~13-14 flat frames (mod delay) before vibrato starts on the HCZ2
melody; a driver whose mod delay only arms on the first note shows ~0-1
flat frames on later notes.

Usage: gate_vib.py capture.vgm
"""
import sys

import numpy as np

import vgmlib as V


def main(path):
    hdr, ev = V.parse(path)
    kos = V.keyons(ev)
    print(f"== gate_vib: {path}")
    print(f"  {'ch':>4} {'notes':>6} {'med flat':>9} {'mean':>6} {'p10':>5} {'p90':>5}  (frames before first fnum move)")
    for ch in range(6):
        fs = V.fnum_stream(ev, ch)
        ons = [t for t, c, on, _ in kos if c == ch and on]
        if not ons or not fs:
            continue
        ftimes = np.array([t for t, _, _ in fs], dtype=np.float64)
        fvals = [(b, f) for _, b, f in fs]
        flat = []
        for i, t_on in enumerate(ons):
            t_next = ons[i + 1] if i + 1 < len(ons) else hdr["end_t"]
            # base pitch = last fnum applied at/just after key-on
            j0 = np.searchsorted(ftimes, t_on + V.FRAME // 2, side="right") - 1
            if j0 < 0:
                continue
            base = fvals[j0]
            # first CHANGE strictly after key-on window, before next note
            j = j0 + 1
            moved = None
            while j < len(fvals) and ftimes[j] < t_next:
                if fvals[j] != base:
                    moved = ftimes[j]
                    break
                j += 1
            if moved is None:
                flat.append((t_next - t_on) / V.FRAME)  # never moved (short note)
            else:
                flat.append((moved - t_on) / V.FRAME)
        if flat:
            a = np.array(flat)
            print(f"  FM{ch} {len(a):>6} {np.median(a):>9.1f} {a.mean():>6.1f} "
                  f"{np.percentile(a,10):>5.1f} {np.percentile(a,90):>5.1f}")


if __name__ == "__main__":
    main(sys.argv[1])
