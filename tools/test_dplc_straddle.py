#!/usr/bin/env python3
"""Unit tests for tools/dplc_straddle.py's DERIVATION.

Split the same way bganim_room's tests are (build.sh:62-74): these test the
MATH over hand-built inputs and never open a `.lst`, because build.sh's pytest
lane runs BEFORE sigil and a listing-reading test there would measure a previous
build. The listing-reading half is the post-sigil `--gate` in build.sh.

Every expectation below is DERIVED from the format spec in
engine/objects/dplc.emp and the split arithmetic in
engine/system/dma_queue.emp, and written out longhand in the test, not copied
from a run of the tool.
"""

import struct
import unittest

import dplc_straddle as D


def make_dplc(frames):
    """Build an S2-format DPLC blob from [[(start, count), ...], ...]."""
    n = len(frames)
    table, body, off = [], b"", n * 2
    for ents in frames:
        table.append(off)
        body += struct.pack(">H", len(ents))
        for start, count in ents:
            body += struct.pack(">H", ((count - 1) << 12) | start)
        off += 2 + 2 * len(ents)
    return b"".join(struct.pack(">H", o) for o in table) + body


class TestStraddle(unittest.TestCase):
    """`straddles` must agree with dma_queue.emp `.transfer`'s borrow test."""

    B = 0x20000

    def test_wholly_inside_a_region_does_not_straddle(self):
        self.assertFalse(D.straddles(0x20000, 32, self.B))
        self.assertFalse(D.straddles(0x3FF00, 0x100, self.B))

    def test_ending_exactly_on_the_boundary_does_not_straddle(self):
        # 0 - len - src borrows only when src+len EXCEEDS the boundary; landing
        # on it exactly leaves the 16-bit sum at zero, so `blo` does not fire.
        self.assertFalse(D.straddles(0x3FFE0, 32, self.B))

    def test_one_byte_past_the_boundary_straddles(self):
        self.assertTrue(D.straddles(0x3FFE0, 33, self.B))
        self.assertTrue(D.straddles(0x3FFFF, 2, self.B))

    def test_starting_on_the_boundary_does_not_straddle(self):
        self.assertTrue(D.straddles(0x3FFE0 + 1, 32, self.B))
        self.assertFalse(D.straddles(0x40000, 32, self.B))

    def test_a_full_16_tile_entry_at_the_worst_offset(self):
        # The largest a DPLC entry can be is 16 tiles = 512 B (the 4-bit count
        # field). Placed so its last byte is the boundary's first, it straddles.
        self.assertTrue(D.straddles(self.B - 511, 512, self.B))
        self.assertFalse(D.straddles(self.B - 512, 512, self.B))


class TestParse(unittest.TestCase):
    def test_round_trip(self):
        frames = [[(0, 1)], [(5, 16), (100, 3)], [(4095, 1)]]
        self.assertEqual(D.parse_dplc(make_dplc(frames), "t"), frames)

    def test_count_field_is_stored_minus_one(self):
        # Entry word bits 15-12 = tile_count-1, so a 16-tile entry stores $F.
        blob = make_dplc([[(0x123, 16)]])
        word = struct.unpack_from(">H", blob, 2 + 2)[0]
        self.assertEqual(word >> 12, 0xF)
        self.assertEqual(word & 0x0FFF, 0x123)

    def test_a_truncated_blob_is_unmeasurable_not_zero(self):
        with self.assertRaises(D.Unmeasurable):
            D.parse_dplc(b"\x00", "t")
        with self.assertRaises(D.Unmeasurable):
            D.parse_dplc(make_dplc([[(0, 1)]])[:-1], "t")


class TestFrameCosts(unittest.TestCase):
    B = 0x20000
    TS = 32

    def test_slot_cost_equals_entries_when_nothing_straddles(self):
        frames = [[(0, 1), (1, 1), (2, 1)]]
        costs = D.frame_costs(frames, 0x1000, self.TS, self.B)
        self.assertEqual(costs[0][0], 3)
        self.assertEqual(costs[0][1], 3)
        self.assertEqual(costs[0][2], [])

    def test_a_straddling_entry_costs_two_slots(self):
        # Base chosen so tile 1 spans the boundary: base + 1*32 = 0x1FFF0,
        # so the entry covers 0x1FFF0..0x20010 and crosses.
        base = 0x1FFF0 - 32
        frames = [[(0, 1), (1, 1)]]
        costs = D.frame_costs(frames, base, self.TS, self.B)
        self.assertEqual(costs[0][0], 2, "two entries")
        self.assertEqual(costs[0][1], 3, "the straddling one is split into two queue entries")
        self.assertEqual(costs[0][2], [1])

    def test_moving_the_base_moves_the_straddle(self):
        """The whole point: the slot cost is a function of PLACEMENT."""
        frames = [[(0, 1), (1, 1)]]
        at = 0x1FFF0 - 32
        self.assertEqual(D.frame_costs(frames, at, self.TS, self.B)[0][1], 3)
        # Shift the base one tile earlier: the entry that straddled now does not.
        self.assertEqual(D.frame_costs(frames, at - 32, self.TS, self.B)[0][1], 2)


class TestRecut(unittest.TestCase):
    TS = 32

    def _sub(self, frames, art_len):
        return {"frames": frames, "art_len": art_len, "art_base": 0,
                "dplc_len": len(make_dplc(frames)), "name": "t"}

    def test_only_frames_over_the_wall_are_rewritten(self):
        frames = [[(0, 1)] * 3, [(0, 1)] * 5]
        nf, grew, dd, rw = D.recut(self._sub(frames, 32 * 100), wall=4, tile_size=self.TS)
        self.assertEqual(rw, [1])
        self.assertEqual(nf[0], frames[0], "the under-wall frame is untouched")

    def test_the_rewrite_appends_and_preserves_the_tile_total(self):
        frames = [[(7, 1)] * 20]           # 20 entries, 20 tiles
        sub = self._sub(frames, 32 * 100)  # art is 100 tiles, so append at tile 100
        nf, grew, dd, rw = D.recut(sub, wall=10, tile_size=self.TS)
        self.assertEqual(sum(c for _, c in nf[0]), 20, "same tile count")
        self.assertEqual(grew, 20 * 32, "20 tiles appended")
        # 20 tiles at <=16 per entry = 2 entries, so 18 entry words vanish.
        self.assertEqual(nf[0], [(100, 16), (116, 4)])
        self.assertEqual(dd, -18 * 2)

    def test_an_entry_never_exceeds_the_4_bit_count_field(self):
        frames = [[(0, 1)] * 40]
        nf, _, _, _ = D.recut(self._sub(frames, 0), wall=10, tile_size=self.TS)
        self.assertTrue(all(c <= 16 for _, c in nf[0]),
                        "bits 15-12 hold count-1, so 16 tiles is the cap")


class TestLoudOnUnmeasurable(unittest.TestCase):
    def test_a_missing_constant_raises(self):
        with self.assertRaises(D.Unmeasurable):
            D.const_from_emp("engine/system/constants.emp", "NOT_A_REAL_CONSTANT")

    def test_a_missing_listing_raises(self):
        with self.assertRaises(D.Unmeasurable):
            D.lst_labels("/nonexistent/never.lst")

    def test_the_boundary_derivation_reads_the_live_source(self):
        # Not an assertion about the VALUE so much as that it is DERIVED: if
        # dma_queue.emp stops spelling the split test, this raises instead of
        # returning a stale 0x20000.
        self.assertEqual(D.boundary_from_source(), 1 << 17)


if __name__ == "__main__":
    unittest.main()
