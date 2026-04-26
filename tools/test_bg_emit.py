"""Tests for BG layout emission (§2 A.5)."""

import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ojz_strip_gen import (
    BLOCK_MAP_PATH,
    CHUNK_MAP_PATH,
    emit_zone_bg_layout,
    load_block_map,
    load_chunk_map,
)


class TestZoneBgEmit(unittest.TestCase):
    def setUp(self):
        self.chunks = load_chunk_map(CHUNK_MAP_PATH)
        self.blocks = load_block_map(BLOCK_MAP_PATH)

    def test_zone_bg_layout_is_64_by_32(self):
        """T1 zone-wide BG layout: full Plane B nametable size = 4096 bytes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "zone_bg.bin")
            emit_zone_bg_layout(self.chunks, self.blocks, out_path)
            self.assertTrue(os.path.isfile(out_path))
            self.assertEqual(
                os.path.getsize(out_path), 64 * 32 * 2,
                "Zone BG layout must be exactly 4096 bytes (64×32 nametable words)",
            )

    def test_zone_bg_layout_words_below_1536(self):
        """Each tile_index field must stay below 1536 (Plane A nametable starts at 1536)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "zone_bg.bin")
            emit_zone_bg_layout(self.chunks, self.blocks, out_path)
            with open(out_path, "rb") as f:
                data = f.read()
            for i in range(0, len(data), 2):
                word = struct.unpack(">H", data[i:i + 2])[0]
                tile_index = word & 0x07FF
                self.assertLess(
                    tile_index, 1536,
                    f"BG word {i // 2} has tile_index {tile_index} ≥ 1536 (would collide with Plane A nametable)",
                )

    def test_zone_bg_layout_strips_priority_bit(self):
        """BG must stay low-priority — priority bit (0x8000) must be cleared on every word."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "zone_bg.bin")
            emit_zone_bg_layout(self.chunks, self.blocks, out_path)
            with open(out_path, "rb") as f:
                data = f.read()
            for i in range(0, len(data), 2):
                word = struct.unpack(">H", data[i:i + 2])[0]
                self.assertEqual(
                    word & 0x8000, 0,
                    f"BG word {i // 2} = 0x{word:04X} has priority bit set",
                )


if __name__ == "__main__":
    unittest.main()
