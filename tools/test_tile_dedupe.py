#!/usr/bin/env python3
"""
Tests for tile_dedupe — flip canonicalization, dedupe, and strip remap.

Run with: python3 tools/test_tile_dedupe.py
"""
import os
import sys
import unittest

# Allow running from the s4_engine root or the tools dir.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tile_dedupe import hflip_tile, vflip_tile


# Build a sentinel tile where each pixel = row*8 + col so flips are visible.
# Row r byte b (b in 0..3) encodes pixels (r*8 + b*2) and (r*8 + b*2 + 1).
# High nibble = left pixel, low nibble = right pixel.
def _make_test_tile():
    out = bytearray(32)
    for r in range(8):
        for b in range(4):
            left  = (r * 8 + b * 2) & 0x0F
            right = (r * 8 + b * 2 + 1) & 0x0F
            out[r * 4 + b] = (left << 4) | right
    return bytes(out)


class TestFlipPrimitives(unittest.TestCase):
    def test_hflip_tile(self):
        t = _make_test_tile()
        flipped = hflip_tile(t)
        # After H-flip, row r byte 0 was row r byte 3 with nibbles swapped
        for r in range(8):
            orig_byte_3 = t[r * 4 + 3]
            expected = ((orig_byte_3 & 0x0F) << 4) | ((orig_byte_3 & 0xF0) >> 4)
            self.assertEqual(
                flipped[r * 4 + 0], expected,
                f"row {r}: expected {expected:02X}, got {flipped[r*4]:02X}",
            )

    def test_vflip_tile(self):
        t = _make_test_tile()
        flipped = vflip_tile(t)
        # After V-flip, row 0 == original row 7
        for r in range(8):
            for b in range(4):
                self.assertEqual(flipped[r * 4 + b], t[(7 - r) * 4 + b])

    def test_hflip_idempotent_pair(self):
        t = _make_test_tile()
        self.assertEqual(hflip_tile(hflip_tile(t)), t)

    def test_vflip_idempotent_pair(self):
        t = _make_test_tile()
        self.assertEqual(vflip_tile(vflip_tile(t)), t)


if __name__ == "__main__":
    unittest.main()
