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

from tile_dedupe import hflip_tile, vflip_tile, canonical_form, dedupe_tiles


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


class TestCanonicalForm(unittest.TestCase):
    def test_canonical_form_picks_smallest(self):
        """canonical_form returns the lex-smallest of the 4 orientations."""
        t = _make_test_tile()
        h = hflip_tile(t)
        v = vflip_tile(t)
        hv = hflip_tile(v)
        smallest = min([t, h, v, hv])
        canon, flip_bits = canonical_form(t)
        self.assertEqual(canon, smallest)
        # Verify flip_bits maps from the original to the canonical
        rebuilt = t
        if flip_bits & 1:
            rebuilt = hflip_tile(rebuilt)
        if flip_bits & 2:
            rebuilt = vflip_tile(rebuilt)
        self.assertEqual(rebuilt, canon)

    def test_canonical_form_horizontal_partner(self):
        """An H-flipped tile and its original share the same canonical form."""
        t = _make_test_tile()
        h = hflip_tile(t)
        canon_t, _ = canonical_form(t)
        canon_h, _ = canonical_form(h)
        self.assertEqual(canon_t, canon_h)


class TestDedupeTiles(unittest.TestCase):
    def test_dedupe_tiles_collapses_flips(self):
        t = _make_test_tile()
        h = hflip_tile(t)
        different = bytes([0xAA] * 32)  # not a flip of t
        inputs = [t, h, t, different]   # tile 0 and 1 are H-flips; tile 2 dup of 0
        unique, mapping = dedupe_tiles(inputs)
        # Two unique canonical forms: canonical(t) and 'different'
        self.assertEqual(len(unique), 2)
        # Tiles 0, 1, 2 all map to the same canonical index
        self.assertEqual(mapping[0][0], mapping[1][0])
        self.assertEqual(mapping[1][0], mapping[2][0])
        # Tile 3 maps to the other canonical index
        self.assertNotEqual(mapping[3][0], mapping[0][0])
        # Tile 0 and tile 1 differ by exactly the H flip bit
        self.assertEqual(mapping[0][1] ^ mapping[1][1], 1)

    def test_dedupe_tiles_first_seen_order(self):
        """Unique tiles emitted in first-seen-canonical order."""
        t1 = bytes([0x11] * 32)  # palindromic — already canonical
        t2 = bytes([0x22] * 32)  # palindromic — already canonical
        unique, _ = dedupe_tiles([t1, t2, t1])
        self.assertEqual(unique, [t1, t2])


if __name__ == "__main__":
    unittest.main()
