#!/usr/bin/env python3
"""Tests for parallax_hscroll_probe — the derivation, the checker, and the smoothness metric.

NO EMULATOR HERE. Every function under test is pure: config bytes and live word values in,
expected HScroll words out. The emulator-backed arms are exercised by running the probe; what
these tests pin is the ARITHMETIC, which is the half that can be wrong silently.

The expected values below are derived in each test's own comment from the engine source, never
copied from a probe run. Two gate expectations copied from a nearby pin would have passed
incorrect code twice in this tree.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parallax_hscroll_probe import (            # noqa: E402
    BE_DSHIFT_A, BE_DSHIFT_B, BE_PHASE, BE_SIZE, BE_TOP,
    CFG_ANCHOR_CH, CFG_ANCHOR_DSA, CFG_ANCHOR_DSB, CFG_BAND_COUNT,
    CFG_DEFORM_TAB_BG, CFG_DEFORM_TAB_FG, CFG_SIZE,
    ANCHOR_NONE, HSCROLL_BYTES, HSCROLL_LINES, NO_DEFORM,
    _patch_band, buffer_pairs, check, curve_ramp, derive_hscroll, derive_shadow,
    pack_pairs, resolve_anchor_line, s16, s8, smoothness, u16,
)


def mkcfg(tops, *, dsa=NO_DEFORM, dsb=NO_DEFORM, tab_fg=0, tab_bg=0,
          anchor=ANCHOR_NONE, adsa=NO_DEFORM, adsb=NO_DEFORM, phase=0):
    """A parallax_config + band array, laid out per engine/structs.emp:161-190."""
    h = bytearray(CFG_SIZE)
    h[CFG_BAND_COUNT] = len(tops)
    h[CFG_ANCHOR_CH] = anchor
    h[CFG_ANCHOR_DSA] = adsa
    h[CFG_ANCHOR_DSB] = adsb
    h[CFG_DEFORM_TAB_FG:CFG_DEFORM_TAB_FG + 4] = tab_fg.to_bytes(4, "big")
    h[CFG_DEFORM_TAB_BG:CFG_DEFORM_TAB_BG + 4] = tab_bg.to_bytes(4, "big")
    body = bytearray()
    # `tops` are PLANE LINES (0..511) since P3 Task 7 — the field was a u8 cell row before.
    for t in tops:
        e = bytearray(BE_SIZE)
        e[BE_TOP:BE_TOP + 2] = t.to_bytes(2, "big")
        e[BE_DSHIFT_A] = dsa
        e[BE_DSHIFT_B] = dsb
        e[BE_PHASE] = phase
        body += e
    return bytes(h) + bytes(body)


class TestLayout(unittest.TestCase):
    def test_buffer_size_matches_ram_declaration(self):
        # engine/ram.emp:270 — `Hscroll_Buffer: [u8; 896]`, 224 lines x 4 bytes.
        self.assertEqual(HSCROLL_BYTES, 896)
        self.assertEqual(HSCROLL_LINES * 4, HSCROLL_BYTES)

    def test_sign_helpers(self):
        self.assertEqual(s8(0xFF), -1)
        self.assertEqual(s8(0x80), -128)
        self.assertEqual(s8(0x7F), 127)
        self.assertEqual(s16(0xFFD0), -48)
        self.assertEqual(u16(-48), 0xFFD0)


# (TestModeKey — the per-line-iff-table-or-anchor transcription — was deleted 2026-08-26
# with the runtime mode key itself, d-29-corrected. There is one fill and no key.)


class TestShadowRotation(unittest.TestCase):
    """Step 4a — engine/level/parallax.emp:687-770."""

    def test_vs_zero_is_the_identity(self):
        # No unit conversion survives: a plane line at vs = 0 IS the screen line.
        sh = derive_shadow(mkcfg([0, 64, 160]), 0, [1, 2, 3, 0], [4, 5, 6, 0], None)
        self.assertEqual(sh.tops, [0, 64, 160])
        self.assertEqual(sh.scroll_a, [1, 2, 3])
        self.assertEqual(sh.scroll_b, [4, 5, 6])

    def test_clamp_at_224_lines_becomes_a_zero_length_band(self):
        # A raw plane-space top of 320 lines would make the filler emit 320 lines and spray
        # past Hscroll_Buffer into the DMA queues; Step 4a clamps at 224 SCREEN LINES.
        sh = derive_shadow(mkcfg([0, 320]), 0, [1, 2], [3, 4], None)
        self.assertEqual(sh.tops, [0, 224])
        self.assertEqual(sh.spans()[1], (224, 224))

    def test_rotation_reorders_bands_and_rebases_tops(self):
        # vscroll_bg = -48 -> (0xFFD0 & 0x1FF) = 464 plane lines.
        # Tops 0/64/320/384 (the shipped OJZ layers' plane images): the last top <= 464 is
        # 384, so k = 3 and the copy order is 3, 0, 1, 2. Band 3 takes the screen top;
        # 0 -> 0-464 = -464 -> +512 = 48; 64 -> -400 -> 112; 320 -> -144 -> 368, clamped 224.
        sh = derive_shadow(mkcfg([0, 64, 320, 384]), 0xFFD0, [10, 11, 12, 13],
                           [20, 21, 22, 23], None)
        self.assertEqual(sh.tops, [0, 48, 112, 224])
        self.assertEqual(sh.scroll_a, [13, 10, 11, 12])
        self.assertEqual(sh.scroll_b, [23, 20, 21, 22])

    def test_the_partial_offset_survives_p3_re_glue(self):
        """THE MECHANISM. A sub-cell Vscroll_BG must move the tops by that many LINES.

        Before world-Y re-glue Step 4a computed `vshift = Vscroll_BG >> 3`, so every value
        of Vscroll_BG inside one 8-px cell produced IDENTICAL tops — the band edge sat still
        while the art under it moved, then jumped a whole cell. This is the regression test
        for that: three vs values one line apart must give three tops one line apart, and
        the old `>> 3` form would return the same list all three times.
        """
        got = [derive_shadow(mkcfg([0, 64, 320, 384]), vs, [10, 11, 12, 13],
                             [20, 21, 22, 23], None).tops[1]
               for vs in (16, 17, 18)]
        self.assertEqual(got, [48, 47, 46])


class TestAnchorOverlay(unittest.TestCase):
    """Step 4b — engine/level/parallax.emp:887-993."""

    def test_split_inserts_one_band_and_overrides_the_shifts_below(self):
        # Continuing the rotation above with L = 80: the last shadow top <= 80 is 48, so k = 1,
        # the split entry lands at index 2 retopped to 80, and every band from 2 down takes
        # pcfg_anchor_dsa/dsb. Tops become 0/48/80/112/224 — the shape the shipped config
        # produces at the idle camera.
        cfg = mkcfg([0, 64, 320, 384], anchor=0, adsa=NO_DEFORM, adsb=2)
        sh = derive_shadow(cfg, 0xFFD0, [10, 11, 12, 13], [20, 21, 22, 23], 80)
        self.assertEqual(sh.tops, [0, 48, 80, 112, 224])
        self.assertEqual(sh.n, 5)
        self.assertEqual(sh.dsb, [NO_DEFORM, NO_DEFORM, 2, 2, 2])
        self.assertEqual(sh.dsa, [NO_DEFORM] * 5)
        # The split entry INHERITS its parent's scroll words — the surface changes where the
        # wave starts, not how the layer scrolls (parallax.emp:955-975).
        self.assertEqual(sh.scroll_a, [13, 10, 10, 11, 12])
        self.assertEqual(sh.scroll_b, [23, 20, 20, 21, 22])

    def test_split_at_line_zero_puts_every_band_under_the_anchor(self):
        cfg = mkcfg([0, 64], anchor=0, adsb=2)
        sh = derive_shadow(cfg, 0, [1, 2], [3, 4], 0)
        self.assertEqual(sh.tops[0:2], [0, 0])
        self.assertEqual(sh.dsb[1:], [2, 2])


class TestAnchorResolution(unittest.TestCase):
    """resolve_anchor_line — engine/level/parallax.emp:802-885."""

    def _tab(self, ch, lo, hi, count=1):
        b = bytearray(count.to_bytes(2, "big"))
        b += (0x8000 | ch).to_bytes(2, "big")
        b += u16(lo).to_bytes(2, "big") + u16(hi).to_bytes(2, "big")
        b += b"\x00\x00\x00\x00"                     # rec_off, rec_len
        return bytes(b)

    def test_no_anchor_means_no_split(self):
        L, why = resolve_anchor_line(mkcfg([0]), [0, 0, 0, 0], None)
        self.assertIsNone(L)
        self.assertIn("no anchor", why)

    def test_off_the_top_splits_at_line_zero_and_is_not_band_clamped(self):
        # L <= 0 is answered by `.anchor_top` BEFORE Raster_GetChannelBand is consulted
        # (parallax.emp:817-830): the palette side covers the whole screen from the frame top,
        # so clamping here too would make the two disagree across exactly those rows.
        cfg = mkcfg([0], anchor=0)
        L, _ = resolve_anchor_line(cfg, [u16(-96), 0, 0, 0], self._tab(0, 40, 200))
        self.assertEqual(L, 0)

    def test_below_the_band_floor_clamps_up(self):
        # fire lines -> screen lines is +1 on both bounds (parallax.emp:850-851).
        cfg = mkcfg([0], anchor=0)
        L, why = resolve_anchor_line(cfg, [20, 0, 0, 0], self._tab(0, 40, 200))
        self.assertEqual(L, 41)
        self.assertIn("clamped", why)

    def test_past_the_band_ceiling_does_not_split_at_all(self):
        # Past band_hi the channel's raster record is not EMITTED, so there is no palette
        # boundary to pin to and the scroll bands must not split either.
        cfg = mkcfg([0], anchor=0)
        L, why = resolve_anchor_line(cfg, [210, 0, 0, 0], self._tab(0, 40, 200))
        self.assertIsNone(L)
        self.assertIn("past band_hi", why)

    def test_inside_the_band_is_unclamped(self):
        cfg = mkcfg([0], anchor=0)
        L, why = resolve_anchor_line(cfg, [128, 0, 0, 0], self._tab(0, 40, 200))
        self.assertEqual(L, 128)
        self.assertIn("unclamped", why)

    def test_no_table_leaves_the_anchor_unclamped(self):
        cfg = mkcfg([0], anchor=0)
        self.assertEqual(resolve_anchor_line(cfg, [128, 0, 0, 0], None)[0], 128)

    def test_patch_walk_matches_only_its_own_channel(self):
        tab = bytearray((2).to_bytes(2, "big"))
        tab += (0x8000 | 1).to_bytes(2, "big") + (11).to_bytes(2, "big") \
            + (111).to_bytes(2, "big") + b"\x00" * 4
        tab += (0x8000 | 0).to_bytes(2, "big") + (22).to_bytes(2, "big") \
            + (222).to_bytes(2, "big") + b"\x00" * 4
        self.assertEqual(_patch_band(bytes(tab), 0), (True, 22, 222))
        self.assertEqual(_patch_band(bytes(tab), 1), (True, 11, 111))
        self.assertEqual(_patch_band(bytes(tab), 2), (False, 0, 0))


class TestDeriveHscroll(unittest.TestCase):
    def test_flat_bands_are_per_band_constants(self):
        cfg = mkcfg([0, 112], tab_fg=0x1000)         # per-line mode, but shift 15 = no sampling
        sh = derive_shadow(cfg, 0, [u16(-96), u16(-48)], [u16(-24), u16(-12)], None)
        exp = derive_hscroll(cfg, sh, bytes(256), None, 0, 0, 0, 0)
        self.assertEqual(len(exp), HSCROLL_LINES)
        self.assertTrue(all(p == (u16(-96), u16(-24)) for p in exp[:112]))
        self.assertTrue(all(p == (u16(-48), u16(-12)) for p in exp[112:]))

    def test_no_table_no_anchor_still_writes_all_224_lines(self):
        """A bare config (no table, no anchor) used to select the per-cell filler and a
        28-entry expectation; since 2026-08-26 (d-29-corrected) there is one filler, and
        the expectation is 224 flat lines split at the shadow tops."""
        cfg = mkcfg([0, 112])
        sh = derive_shadow(cfg, 0, [1, 2], [3, 4], None)
        exp = derive_hscroll(cfg, sh, None, None, 0, 0, 0, 0)
        self.assertEqual(len(exp), HSCROLL_LINES)
        self.assertTrue(all(p == (1, 3) for p in exp[:112]))
        self.assertTrue(all(p == (2, 4) for p in exp[112:]))

    def test_bg_sampling_uses_phase_plus_vscroll_plus_line_mod_256(self):
        # BG index = (Parallax_Deform_Phase_BG + band_phase + Vscroll_BG + line) & $FF, sample
        # sign-extended and arithmetic-shifted right by band_deform_shift_b, added to the band's
        # scroll word (parallax.emp:1344-1371). Table[i] = i - 128 makes the sample readable:
        # at phase 10, vscroll 0, line 0 -> index 10 -> sample -118 -> >> 2 = -30 (arithmetic,
        # so it floors: -118 >> 2 == -30). Base -48 -> -78.
        tab = bytes(((i - 128) & 0xFF) for i in range(256))
        cfg = mkcfg([0], tab_bg=0x1000, dsb=2)
        sh = derive_shadow(cfg, 0, [u16(-96)], [u16(-48)], None)
        exp = derive_hscroll(cfg, sh, None, tab, 0, 10, 0, 0)
        self.assertEqual(s16(exp[0][1]), -48 + (-118 >> 2))
        self.assertEqual(s16(exp[1][1]), -48 + (-117 >> 2))
        self.assertEqual(s16(exp[0][0]), -96)         # FG untouched: no FG table
        # The index wraps at 256 (`andi.w #$FF, d1`), and nothing else does. At phase 200 the
        # wrap lands at line 56, inside the 224 the buffer holds.
        exp2 = derive_hscroll(cfg, sh, None, tab, 0, 200, 0, 0)
        self.assertEqual(s16(exp2[55][1]), -48 + (s8(tab[255]) >> 2))
        self.assertEqual(s16(exp2[56][1]), -48 + (s8(tab[0]) >> 2))

    def test_fg_sampling_folds_camera_y_and_bg_folds_vscroll(self):
        # The layer anchor (Harmony study defect #2): the FG index folds Camera_Y's pixel high
        # word, the BG index folds Parallax_Current_Vscroll_BG, so the wave rides the ART.
        tab = bytes(((i - 128) & 0xFF) for i in range(256))
        cfg = mkcfg([0], tab_fg=0x1000, tab_bg=0x2000, dsa=1, dsb=1)
        sh = derive_shadow(cfg, 0, [0], [0], None)
        exp = derive_hscroll(cfg, sh, tab, tab, 0, 0, 7, 0)      # cam_y_hi = 7
        self.assertEqual(s16(exp[0][0]), s8(tab[7]) >> 1)        # FG index shifted by camY
        self.assertEqual(s16(exp[0][1]), s8(tab[0]) >> 1)        # BG index not
        exp2 = derive_hscroll(cfg, sh, tab, tab, 0, 0, 0, 7)     # vscroll_bg = 7
        self.assertEqual(s16(exp2[0][0]), s8(tab[0]) >> 1)
        self.assertEqual(s16(exp2[0][1]), s8(tab[7]) >> 1)

    def test_a_null_table_disables_its_channel_even_at_a_live_shift(self):
        cfg = mkcfg([0], tab_bg=0x1000, dsa=2, dsb=2)            # FG shift live, FG table NULL
        sh = derive_shadow(cfg, 0, [u16(-96)], [u16(-48)], None)
        tab = bytes([100] * 256)
        exp = derive_hscroll(cfg, sh, None, tab, 0, 0, 0, 0)
        self.assertEqual(s16(exp[0][0]), -96)
        self.assertEqual(s16(exp[0][1]), -48 + (100 >> 2))


class TestChecker(unittest.TestCase):
    def test_identical_sequences_are_green(self):
        exp = [(1, 2)] * 10
        ok, bad = check(exp, exp)
        self.assertTrue(ok)
        self.assertEqual(bad, [])

    def test_a_single_wrong_word_is_named_by_line_and_channel(self):
        # A gate that reports only "something differed" is the failure mode design §8.5 forbids.
        exp = [(0x1000, 0x2000)] * 10
        act = [list(p) for p in exp]
        act[7][1] = 0x2001
        ok, bad = check([tuple(p) for p in act], exp)
        self.assertFalse(ok)
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 7)
        self.assertEqual(bad[0]["chan"], "BG")
        self.assertEqual(bad[0]["expected"], 0x2000)
        self.assertEqual(bad[0]["got"], 0x2001)

    def test_both_channels_of_a_line_are_reported_separately(self):
        ok, bad = check([(1, 1)], [(2, 2)])
        self.assertFalse(ok)
        self.assertEqual([m["chan"] for m in bad], ["FG", "BG"])

    def test_unwritten_entries_are_skipped_not_asserted(self):
        # Per-cell mode leaves lines 28..223 stale; an expectation of None must not be checked.
        ok, _ = check([(9, 9), (9, 9)], [(9, 9), None])
        self.assertTrue(ok)

    def test_pack_and_unpack_round_trip_in_vdp_word_order(self):
        pairs = [(0xFFA0, 0xFFD0), (0x0001, 0x0002)]
        raw = pack_pairs(pairs)
        self.assertEqual(raw, bytes.fromhex("FFA0FFD000010002"))
        self.assertEqual(buffer_pairs(raw, 2), pairs)


class TestCurveRamp(unittest.TestCase):
    def test_the_ramp_is_outside_what_any_deform_table_can_emit(self):
        # This is the anti-vacuity argument for the red-first proof, asserted rather than
        # claimed. A deform sample is a SIGNED BYTE, so the very widest excursion a table can
        # produce anywhere on the screen is 127 - (-128) = 255 at shift 0, and the shipped
        # tables are amplitude 8..96 at shift >= 1. If the ramp fitted inside that envelope, a
        # checker could pass it by accident.
        ramp = curve_ramp(0, 0, HSCROLL_LINES)
        bg = [s16(p[1]) for p in ramp]
        self.assertGreater(max(bg) - min(bg), 255)
        self.assertEqual(bg, sorted(bg))                  # monotone: a bow, not a wobble

    def test_the_ramp_has_a_non_constant_second_difference(self):
        # A flat band's first differences are identically 0 and a linear ramp's are constant;
        # a CURVE's are not. The ramp is quadratic so its d1 rises monotonically.
        sm = smoothness(curve_ramp(0, 0, HSCROLL_LINES), [0])
        self.assertGreater(sm["BG"]["interior_max_abs_d1"], 1)
        self.assertGreater(sm["BG"]["interior_d1_max"], sm["BG"]["interior_d1_min"])

    def test_the_ramp_is_anchored_on_the_bases_it_is_given(self):
        ramp = curve_ramp(0x1234, 0x5678, 8)
        self.assertEqual(ramp[0], (0x1234, 0x5678))


class TestSmoothness(unittest.TestCase):
    def test_a_flat_buffer_has_zero_interior_motion(self):
        sm = smoothness([(5, 7)] * 100, [0])
        self.assertEqual(sm["FG"]["interior_nonzero"], 0)
        self.assertEqual(sm["BG"]["interior_max_abs_d1"], 0)
        self.assertEqual(sm["BG"]["interior_max_abs_d2"], 0)

    def test_band_edges_are_excluded_from_the_interior_statistic(self):
        # A band boundary is a legitimate discontinuity: the two bands carry different scroll
        # factors. Folding it into the interior statistic would make every multi-band config
        # look rough and would hide a genuinely jagged curve inside one band.
        pairs = [(0, 0)] * 10 + [(0, 100)] * 10
        sm = smoothness(pairs, [0, 10])
        self.assertEqual(sm["BG"]["interior_max_abs_d1"], 0)
        self.assertEqual(sm["BG"]["edge_max_abs_d1"], 100)
        self.assertEqual(sm["BG"]["edge_steps"], [{"line": 10, "d1": 100}])

    def test_the_first_difference_histogram_counts_every_interior_step(self):
        pairs = [(0, i) for i in range(11)]
        sm = smoothness(pairs, [0])
        self.assertEqual(sm["BG"]["interior_d1_hist"], {1: 10})
        self.assertEqual(sm["BG"]["interior_steps"], 10)

    def test_second_difference_catches_a_kink_a_first_difference_bound_misses(self):
        # Two ramps of equal step, spliced: |d1| never exceeds 2, but the sign flip is a kink.
        # This is the metric T10 needs — a curve can satisfy a step bound and still be jagged.
        pairs = [(0, i * 2) for i in range(20)] + [(0, 36 - i * 2) for i in range(20)]
        sm = smoothness(pairs, [0])
        self.assertEqual(sm["BG"]["interior_max_abs_d1"], 2)
        self.assertEqual(sm["BG"]["interior_max_abs_d2"], 4)


if __name__ == "__main__":
    unittest.main()
