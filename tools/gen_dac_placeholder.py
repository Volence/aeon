#!/usr/bin/env python3
"""Generate a CLEAN TEMP placeholder DAC blip for §1B engine bring-up.

Output: data/sound/temp_blip.bin — raw 8-bit UNSIGNED PCM, centered at $80.

This is a THROWAWAY placeholder. Its only job is to exercise the ROM-streaming /
banking ENGINE with a clean, tonal signal so any engine artifacts (clicks, gaps,
dropouts, banking glitches) are audible against silence/static. The real sample
content (the sonic_hack DPCM-compressed DAC samples) is deferred, user-driven
work — it is NOT decided here.

Signal: a ~440 Hz sine with exponential amplitude decay over ~0.18 s, rendered
at a 16000 Hz sample rate -> ~2880 bytes. Pure python/math, no dependencies.
Samples clamp to 0..255.
"""
import math
import os

SAMPLE_RATE = 16000          # Hz — playback rate the driver targets
DURATION    = 0.18           # seconds
FREQ        = 440.0          # Hz — clean tone (A4)
DECAY       = 14.0           # exponential amplitude decay rate (1/sec)
CENTER      = 128            # $80 — unsigned-PCM zero level
AMPLITUDE   = 120.0          # peak deviation from center (keeps clamp headroom)

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "sound", "temp_blip.bin")


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    length = int(round(SAMPLE_RATE * DURATION))   # ~2880 samples
    samples = bytearray()
    for n in range(length):
        t = n / SAMPLE_RATE
        env = math.exp(-DECAY * t)
        value = CENTER + AMPLITUDE * env * math.sin(2.0 * math.pi * FREQ * t)
        b = int(round(value))
        if b < 0:
            b = 0
        elif b > 255:
            b = 255
        samples.append(b)
    with open(OUT, "wb") as f:
        f.write(samples)
    print(f"wrote {len(samples)} bytes -> {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
