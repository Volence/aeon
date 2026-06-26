# tools/test_import_s3k_dac.py — tests for the S3K DAC wav->raw8 importer.
import os
import struct
import tempfile

import numpy as np

from import_s3k_dac import wav_to_raw8


def _write_u8_wav(path, samples_u8, rate):
    """Write a mono 8-bit unsigned PCM WAV to `path`."""
    import wave
    w = wave.open(path, "wb")
    w.setnchannels(1)
    w.setsampwidth(1)
    w.setframerate(rate)
    w.writeframes(bytes(int(s) & 0xFF for s in samples_u8))
    w.close()


def _write_s16_wav(path, samples_s16, rate):
    """Write a mono 16-bit signed PCM WAV to `path`."""
    import wave
    w = wave.open(path, "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(rate)
    w.writeframes(b"".join(struct.pack("<h", int(s)) for s in samples_s16))
    w.close()


def test_u8_wav_to_raw8_valid_nonempty():
    # A synthetic 8 kHz wav resampled to 18356 Hz yields valid unsigned-8-bit
    # bytes (every value in [0,255]) and is nonempty.
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "tone.wav")
        n = 800
        t = np.arange(n)
        sig = (np.sin(2 * np.pi * 440 * t / 8000) * 100 + 128).astype(np.uint8)
        _write_u8_wav(p, sig, 8000)
        out = wav_to_raw8(p, target_hz=18356, pitch_ratio=1.0)
        assert isinstance(out, (bytes, bytearray))
        assert len(out) > 0
        assert all(0 <= b <= 255 for b in out)


def test_pitch_ratio_2_is_about_half_length():
    # pitch_ratio=2.0 (an octave up) produces ~half the samples of pitch_ratio=1.0:
    # higher pitch = shorter sample.
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "tone.wav")
        n = 1000
        t = np.arange(n)
        sig = (np.sin(2 * np.pi * 300 * t / 8000) * 90 + 128).astype(np.uint8)
        _write_u8_wav(p, sig, 8000)
        base = wav_to_raw8(p, target_hz=18356, pitch_ratio=1.0)
        high = wav_to_raw8(p, target_hz=18356, pitch_ratio=2.0)
        ratio = len(high) / len(base)
        assert 0.45 < ratio < 0.55, "expected ~0.5, got %.3f" % ratio


def test_lower_pitch_is_longer():
    # pitch_ratio<1.0 (lower pitch) lengthens the sample.
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "tone.wav")
        n = 600
        t = np.arange(n)
        sig = (np.sin(2 * np.pi * 200 * t / 8000) * 80 + 128).astype(np.uint8)
        _write_u8_wav(p, sig, 8000)
        base = wav_to_raw8(p, target_hz=18356, pitch_ratio=1.0)
        low = wav_to_raw8(p, target_hz=18356, pitch_ratio=0.5)
        assert len(low) > len(base)


def test_16bit_wav_supported():
    # 16-bit signed WAV input is centered/scaled to valid unsigned-8-bit output.
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "tone16.wav")
        n = 500
        t = np.arange(n)
        sig = (np.sin(2 * np.pi * 440 * t / 8000) * 20000).astype(np.int16)
        _write_s16_wav(p, sig, 8000)
        out = wav_to_raw8(p, target_hz=18356, pitch_ratio=1.0)
        assert len(out) > 0
        assert all(0 <= b <= 255 for b in out)
        # the output should span a meaningful range around the $80 center.
        arr = np.frombuffer(out, dtype=np.uint8)
        assert arr.max() > 0xA0 and arr.min() < 0x60
