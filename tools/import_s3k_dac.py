# tools/import_s3k_dac.py — S3K DAC WAV -> raw-8-bit PCM importer.
#
# The S3K DAC WAV sources play at their native sample rate with a per-id rate
# MULTIPLIER (sonic3k.macros.asm DAC_Setup: e.g. 0.80 = "a fifth slower"). Our
# engine plays ALL DAC samples at a FIXED ~18356 Hz loop rate (ds_rate is
# reserved/ignored), so a sample's pitch must be baked into the .pcm by
# resampling. wav_to_raw8 resamples to the fixed engine rate and bakes the
# pitch in via `pitch_ratio` (pitch_ratio>1 = higher/shorter).
#
# The 4 toms (ids $82..$85) are the SAME 82-85.wav at four S3K rate multipliers
# (1.0 / 0.80 / 0.67 / 0.58); passing those as pitch_ratio reproduces the real
# relative tom tuning. See HCZ2 import Phase 5.
import wave

import numpy as np

from dac_encode import encode_raw8

# Engine fixed DAC loop rate (Hz). All samples are resampled to this; pitch is
# baked in via pitch_ratio (the engine ignores ds_rate).
ENGINE_DAC_HZ = 18356


def _read_wav_centered(path):
    """Read a mono WAV (8-bit unsigned or 16-bit signed) as float centered at 0,
    returning (samples_float, src_rate). 8-bit: value-128. 16-bit: value/256."""
    w = wave.open(path, "rb")
    nch = w.getnchannels()
    width = w.getsampwidth()
    rate = w.getframerate()
    n = w.getnframes()
    raw = w.readframes(n)
    w.close()
    assert nch == 1, "expect mono wav, got %d channels" % nch
    if width == 1:
        data = np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0
    elif width == 2:
        # 16-bit signed -> scale into 8-bit-equivalent range, centered at 0.
        data = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 256.0
    else:
        raise ValueError("unsupported sample width %d bytes (expect 8- or 16-bit)" % width)
    return data, rate


def wav_to_raw8(path, target_hz=ENGINE_DAC_HZ, pitch_ratio=1.0):
    """Read `path`, resample to `target_hz`, bake in `pitch_ratio`, and return raw
    8-bit unsigned PCM bytes (centered $80).

    pitch_ratio > 1 = higher pitch = shorter sample. The effective output length is
    len * (target_hz / src_hz) / pitch_ratio (resample to target_hz, then speed up
    by pitch_ratio)."""
    samples, src_hz = _read_wav_centered(path)
    if len(samples) == 0:
        return b""

    # Output length: resample to target_hz, then speed by pitch_ratio.
    n_out = max(1, int(round(len(samples) * (target_hz / src_hz) / pitch_ratio)))
    # Sample positions in the source for each output index (linear interpolation).
    xs = np.linspace(0.0, len(samples) - 1, n_out)
    resampled = np.interp(xs, np.arange(len(samples)), samples)

    # Back to unsigned 8-bit centered $80, clipped to [0,255].
    out = np.clip(np.round(resampled + 128.0), 0, 255).astype(np.int32)
    return encode_raw8(out)


# ---------------------------------------------------------------------------
# HCZ2 drum set — S3K id, source WAV, and S3K rate multiplier (pitch_ratio).
# Rates from sonic3k.macros.asm DAC_82..DAC_85_Setup (real, not approximated):
#   $82 hi tom   = 1.0   (default)
#   $83 mid tom  = 0.80
#   $84 low tom  = 0.67
#   $85 floor tom= 0.58
# Snare ($81) and kick ($86) are their own samples at multiplier 1.0.
# (out_name, wav_basename, pitch_ratio)
HCZ2_DRUMS = [
    ("s3k_snare",   "81.wav",    1.0),
    ("s3k_hitom",   "82-85.wav", 1.0),
    ("s3k_midtom",  "82-85.wav", 0.80),
    ("s3k_lowtom",  "82-85.wav", 0.67),
    ("s3k_floortom", "82-85.wav", 0.58),
    ("s3k_kick",    "86.wav",    1.0),
]


def main(argv=None):
    import argparse
    import os

    ap = argparse.ArgumentParser(description="Encode the 6 S3K HCZ2 drums to raw-8-bit .pcm")
    ap.add_argument("--src-dir", default="/home/volence/sonic_hacks/skdisasm/Sound/DAC",
                    help="directory holding 81.wav / 82-85.wav / 86.wav")
    ap.add_argument("--out-dir", default="data/sound/dac",
                    help="output directory for the .pcm files")
    ap.add_argument("--rate", type=int, default=ENGINE_DAC_HZ,
                    help="engine fixed DAC loop rate (Hz)")
    a = ap.parse_args(argv)

    os.makedirs(a.out_dir, exist_ok=True)
    for out_name, wav, ratio in HCZ2_DRUMS:
        src = os.path.join(a.src_dir, wav)
        data = wav_to_raw8(src, target_hz=a.rate, pitch_ratio=ratio)
        out_path = os.path.join(a.out_dir, out_name + ".pcm")
        with open(out_path, "wb") as f:
            f.write(data)
        print("%s: %d bytes  (src=%s  pitch_ratio=%.2f)" %
              (out_path, len(data), wav, ratio))


if __name__ == "__main__":
    main()
