#!/usr/bin/env python3
# tools/dac_verify.py — verify a DAC sample really played by cross-correlating the
# captured YM $2A (DAC data) byte stream against the EXPECTED output waveform (a .bin
# of unsigned 8-bit samples — for raw PCM that's the sample bytes; for DPCM that's the
# DECODED output). This is the project's hard rule: never trust "is it non-silent" — an
# enabled DAC on a bad pointer streams structured ROM garbage that looks audible.
#
# Usage: python3 tools/dac_verify.py <capture.vgm> <expected_output.bin>
#   prints: $2A sample count, % $80-silence, best cross-correlation vs the reference,
#           and PLAYS / NOT-the-sample.
import sys, struct
import numpy as np


def dac_stream(vgm_path):
    """Extract the ordered YM2612 port-0 reg $2A (DAC data) byte stream from a VGM."""
    d = open(vgm_path, 'rb').read()
    voff = struct.unpack('<I', d[0x34:0x38])[0]
    i = (0x34 + voff) if voff else 0x40
    n = len(d)
    out = []
    while i < n:
        c = d[i]
        if c == 0x66:              # end of stream
            break
        elif c == 0x52:            # YM2612 port 0 write: reg, val
            if d[i + 1] == 0x2A:
                out.append(d[i + 2])
            i += 3
        elif c == 0x53:            # YM2612 port 1 write
            i += 3
        elif c == 0x50:            # PSG write
            i += 2
        elif c == 0x61:            # wait n samples
            i += 3
        elif c in (0x62, 0x63):    # wait 1/60, 1/50
            i += 1
        elif 0x70 <= c <= 0x8f:    # wait 1..16 / YM2612 DAC+wait
            i += 1
        elif c == 0x67:            # data block
            i += 7 + struct.unpack('<I', d[i + 3:i + 7])[0]
        elif c == 0x4f:            # GG stereo
            i += 2
        elif c == 0xe0:            # seek PCM
            i += 5
        else:
            i += 1
    return np.array(out, dtype=float)


def best_xcorr(dac, ref):
    """Best normalized cross-correlation of the reference over the dac stream."""
    L = len(ref)
    s = ref - ref.mean()
    best = -1.0
    for p in range(0, max(1, len(dac) - L), 7):
        w = dac[p:p + L]
        w = w - w.mean()
        denom = np.sqrt((w * w).sum() * (s * s).sum())
        if denom > 0:
            best = max(best, float((w * s).sum() / denom))
    return best


def main():
    if len(sys.argv) != 3:
        print("usage: dac_verify.py <capture.vgm> <expected_output.bin>")
        sys.exit(2)
    dac = dac_stream(sys.argv[1])
    ref = np.frombuffer(open(sys.argv[2], 'rb').read(), dtype=np.uint8).astype(float)
    if len(dac) == 0:
        print("$2A samples=0 — no DAC data captured (DAC never wrote $2A)")
        print("NOT the sample (silent)")
        sys.exit(1)
    silence = float(np.mean(dac == 128) * 100)
    best = best_xcorr(dac, ref)
    print(f"$2A samples={len(dac)} silence($80)={silence:.0f}% best_xcorr_vs_sample={best:.3f}")
    print("PLAYS" if best > 0.9 else "NOT the sample (garbage/silent)")


if __name__ == "__main__":
    main()
