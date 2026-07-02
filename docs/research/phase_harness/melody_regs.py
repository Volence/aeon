#!/usr/bin/env python3
"""Per-channel key-on vs key-off counts from $28 writes.

The EG-retrigger gate: a driver that keys off before every note shows
key-off count ~= key-on count per melody channel. Ours (baseline) shows
key-off << key-on on bare-note channels.

Usage: melody_regs.py capture.vgm
"""
import sys

import vgmlib as V


def main(path):
    hdr, ev = V.parse(path)
    kos = V.keyons(ev)
    print(f"== melody_regs: {path}")
    print(f"  {'ch':>4} {'key-on':>7} {'key-off':>8} {'off/on':>7}")
    for ch in range(6):
        non = sum(1 for t, c, on, _ in kos if c == ch and on)
        noff = sum(1 for t, c, on, _ in kos if c == ch and not on)
        ratio = noff / non if non else float("nan")
        print(f"  FM{ch:>1} {non:>7} {noff:>8} {ratio:>7.2f}")
    # off-then-on adjacency: how many key-ons were preceded by a key-off on the
    # same channel within 2 frames (the retrigger signature)
    print("key-ons preceded by same-channel key-off within 2 frames (retrigger):")
    win = 2 * V.FRAME
    for ch in range(6):
        seq = [(t, on) for t, c, on, _ in kos if c == ch]
        ons = 0
        retrig = 0
        last_off = None
        for t, on in seq:
            if on:
                ons += 1
                if last_off is not None and t - last_off <= win:
                    retrig += 1
            else:
                last_off = t
        if ons:
            print(f"  FM{ch}: {retrig}/{ons} ({100*retrig/ons:.0f}%)")


if __name__ == "__main__":
    main(sys.argv[1])
