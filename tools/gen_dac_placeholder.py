#!/usr/bin/env python3
"""Generate a CLEAN TEMP placeholder DAC blip for §1B engine bring-up.

Output: data/sound/temp_blip.bin — raw 8-bit UNSIGNED PCM, centered at $80.

This is a THROWAWAY placeholder. Its only job is to exercise the ROM-streaming /
banking ENGINE with a clean, tonal signal so any engine artifacts (pitch wobble,
gaps, dropouts, banking glitches) are audible. The real sample content (the
sonic_hack DPCM samples) is deferred, user-driven work — NOT decided here.

Signal: a STEADY (no envelope) sine of an INTEGER number of periods, so looping is
seamless — the wrap sample[-1] -> sample[0] is the same step as anywhere else in the
wave, with NO amplitude discontinuity and NO repeated attack. (The previous decaying
blip restarted with a loud attack every loop = the "attack pop" the user heard.)
A steady tone is also the right probe for the real goal: verifying the DAC output
rate is rock-steady (constant pitch) under load. Starts and ends at $80 (DC center).
"""
import math
import os

PERIOD_SAMPLES = 16          # samples per sine period (integer -> seamless loop)
NUM_PERIODS    = 180         # total periods -> length = 16*180 = 2880 samples
CENTER         = 128         # $80 — unsigned-PCM zero level
AMPLITUDE      = 100.0       # peak deviation from center (clamp headroom both sides)

OUT = os.path.join(os.path.dirname(__file__), "..", "games", "sonic4", "data", "sound", "temp_blip.bin")


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    length = PERIOD_SAMPLES * NUM_PERIODS          # exact integer periods
    samples = bytearray()
    for n in range(length):
        # phase 0 at n=0 -> sample[0] = CENTER ($80); integer periods -> sample
        # at length wraps back to phase 0, so the loop seam is continuous.
        value = CENTER + AMPLITUDE * math.sin(2.0 * math.pi * n / PERIOD_SAMPLES)
        b = int(round(value))
        b = 0 if b < 0 else 255 if b > 255 else b
        samples.append(b)
    with open(OUT, "wb") as f:
        f.write(samples)
    # report the seam continuity for sanity
    step_seam = abs(samples[0] - samples[-1])
    print(f"wrote {len(samples)} bytes -> {os.path.normpath(OUT)}")
    print(f"  start={samples[0]} end={samples[-1]} seam-step={step_seam} (should match mid-wave step)")


if __name__ == "__main__":
    main()
