#!/usr/bin/env python3
"""
Tests for tile_dedupe — flip canonicalization, dedupe, and strip remap.

Run with: python3 tools/test_tile_dedupe.py
"""
import os
import sys
import unittest

# Allow running from the aeon root or the tools dir.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tile_dedupe import (
    hflip_tile,
    vflip_tile,
    canonical_form,
    dedupe_tiles,
    remap_nametable_word,
    order_pool_spatially,
    split_pool_into_pages,
    NAMETABLE_TILE_MASK,
    NAMETABLE_H_BIT,
    NAMETABLE_V_BIT,
)


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


class TestRemapNametableWord(unittest.TestCase):
    def test_preserves_priority_palette(self):
        # priority=1, palette=2, no flips, tile_index=42
        word = (1 << 15) | (2 << 13) | 42
        new = remap_nametable_word(word, vram_tile_slot=7, canon_flip_bits=0)
        self.assertEqual((new >> 15) & 1, 1, "priority preserved")
        self.assertEqual((new >> 13) & 3, 2, "palette preserved")
        self.assertEqual(new & 0x7FF, 7, "tile_index = canonical_index")
        self.assertEqual((new >> 11) & 1, 0, "H bit unchanged")
        self.assertEqual((new >> 12) & 1, 0, "V bit unchanged")

    def test_xors_flip_bits(self):
        # Original word: H=1, V=0, tile_index=42
        word = (1 << 11) | 42
        # Canonicalization needed an additional H flip
        new = remap_nametable_word(word, vram_tile_slot=7, canon_flip_bits=1)
        self.assertEqual((new >> 11) & 1, 0, "1 ^ 1 = 0 — H now off")
        self.assertEqual((new >> 12) & 1, 0, "V still 0")
        self.assertEqual(new & 0x7FF, 7, "tile_index updated")

    def test_double_flip(self):
        # Original: H=1, V=1, tile=42; canon needs H+V flip
        word = (1 << 12) | (1 << 11) | 42
        new = remap_nametable_word(word, vram_tile_slot=7, canon_flip_bits=3)
        self.assertEqual((new >> 11) & 1, 0)
        self.assertEqual((new >> 12) & 1, 0)
        self.assertEqual(new & 0x7FF, 7)


class TestRoundTrip(unittest.TestCase):
    def test_dedupe_remap_round_trip(self):
        """Dedupe + remap a small tile + nametable set, expand back, byte-compare."""
        t1 = _make_test_tile()
        t2 = hflip_tile(t1)              # H-flipped duplicate of t1
        t3 = bytes([0x55] * 32)          # palindromic — different
        tiles = [t1, t2, t3]
        # Nametable: tile 0 (no flip), tile 1 (no flip), tile 2 (no flip)
        # palette=1, priority=0
        words = [(1 << 13) | i for i in range(3)]

        unique, mapping = dedupe_tiles(tiles)
        new_words = [
            remap_nametable_word(
                w,
                mapping[w & NAMETABLE_TILE_MASK][0],
                mapping[w & NAMETABLE_TILE_MASK][1],
            )
            for w in words
        ]

        def reconstruct(word, pool):
            idx = word & NAMETABLE_TILE_MASK
            h = bool(word & NAMETABLE_H_BIT)
            v = bool(word & NAMETABLE_V_BIT)
            out = pool[idx]
            if h:
                out = hflip_tile(out)
            if v:
                out = vflip_tile(out)
            return out

        for original_idx, new_word in enumerate(new_words):
            rebuilt = reconstruct(new_word, unique)
            self.assertEqual(rebuilt, tiles[original_idx],
                             f"round-trip mismatch at tile {original_idx}")


class TestPackRegions(unittest.TestCase):
    def test_packs_into_first_region_when_fits(self):
        from tile_dedupe import pack_regions
        slots = pack_regions(3, [(0, 1536), (1984, 64)])
        self.assertEqual(slots, [0, 1, 2], "all 3 fit in region 0 starting at slot 0")

    def test_spills_into_second_region_when_first_exhausted(self):
        from tile_dedupe import pack_regions
        slots = pack_regions(5, [(0, 3), (1984, 64)])
        self.assertEqual(
            slots,
            [0, 1, 2, 1984, 1985],
            "first 3 in region 0; remainder starts at region 1's base 1984",
        )

    def test_raises_on_total_overflow(self):
        from tile_dedupe import pack_regions
        with self.assertRaises(OverflowError):
            pack_regions(10, [(0, 3), (1984, 2)])

    def test_skips_zero_capacity_region(self):
        from tile_dedupe import pack_regions
        slots = pack_regions(2, [(0, 0), (1984, 64)])
        self.assertEqual(slots, [1984, 1985])


class TestOrderPoolSpatially(unittest.TestCase):
    def test_preserves_first_seen_order(self):
        per_section = [[0, 1, 2], [2, 3], [1, 4]]
        order = order_pool_spatially(per_section)
        self.assertEqual(order, [0, 1, 2, 3, 4])

    def test_is_a_permutation_of_all_unique(self):
        per_section = [[5, 5, 1], [1, 9, 0]]
        order = order_pool_spatially(per_section)
        self.assertEqual(sorted(order), [0, 1, 5, 9])

    def test_empty_input(self):
        self.assertEqual(order_pool_spatially([]), [])


class TestSplitPoolIntoPages(unittest.TestCase):
    def test_splits_on_page_size(self):
        pool = list(range(600))
        pages = split_pool_into_pages(pool, page_tiles=256)
        self.assertEqual([len(p) for p in pages], [256, 256, 88])

    def test_single_page_when_small(self):
        pages = split_pool_into_pages([1, 2, 3], page_tiles=256)
        self.assertEqual(pages, [[1, 2, 3]])

    def test_empty_input(self):
        self.assertEqual(split_pool_into_pages([], 256), [])


if __name__ == "__main__":
    unittest.main()
