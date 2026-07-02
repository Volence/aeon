#!/usr/bin/env python3
"""Capture purity gate: per-second key-on histogram + channel content.

Usage: clean_purity.py capture.vgm

PASS heuristics for a clean single-song HCZ2 capture:
- key-on traffic starts once and stays steady (no mid-capture burst = 2nd song)
- FM melody channels show dense note traffic; DAC ($2A) and PSG noise active
"""
import sys
from collections import Counter

import vgmlib as V


def main(path):
    hdr, ev = V.parse(path)
    dur = hdr["end_t"] / V.RATE
    print(f"== purity: {path}")
    print(f"duration: {dur:.1f}s  events: {len(ev)}")

    kos = V.keyons(ev)
    ons = [(t, ch) for t, ch, on, _ in kos if on]
    offs = [(t, ch) for t, ch, on, _ in kos if not on]

    # per-second key-on histogram
    hist = Counter(int(t / V.RATE) for t, _ in ons)
    secs = int(dur) + 1
    line = "".join(f"{hist.get(s, 0):3d}" for s in range(secs))
    print("per-second key-ons:")
    for i in range(0, secs, 20):
        print(f"  s{i:3d}: " + "".join(f"{hist.get(s,0):4d}" for s in range(i, min(i + 20, secs))))
    vals = [hist.get(s, 0) for s in range(secs)]
    active = [v for v in vals if v > 0]
    if active:
        import statistics as st
        mean = st.mean(active)
        peak = max(active)
        print(f"active seconds: {len(active)}/{secs}  mean={mean:.1f}/s peak={peak}/s "
              f"peak/mean={peak/mean:.2f}  (contamination flag if a sudden burst >>2x mean)")

    # per-channel content
    print("per-FM-channel key-on/off counts:")
    for ch in range(6):
        non = sum(1 for _, c in ons if c == ch)
        noff = sum(1 for _, c in offs if c == ch)
        print(f"  FM{ch}: on={non:4d} off={noff:4d}")

    dw = V.dac_writes(ev)
    print(f"DAC $2A writes: {len(dw)}")
    psg = [e for e in ev if e.kind == "psg"]
    noise_ctrl = [e.a for e in psg if (e.a & 0xF0) == 0xE0]
    print(f"PSG writes: {len(psg)}  noise-control writes: {len(noise_ctrl)} "
          f"modes: {sorted(set(v & 0x0F for v in noise_ctrl))}")
    first_on = ons[0][0] / V.RATE if ons else None
    print(f"first key-on at t={first_on:.2f}s" if first_on is not None else "NO KEY-ONS")


if __name__ == "__main__":
    main(sys.argv[1])
