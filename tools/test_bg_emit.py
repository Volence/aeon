"""Tests for BG layout + shared BG tile region emission (§2 A.5 T1)."""

import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ojz_strip_gen import (
    BLOCK_MAP_PATH,
    CHUNK_MAP_PATH,
    LAYOUT_DIR,
    OJZ_ART_PATH,
    BG_TILE_BASE_SLOT,
    PLANE_B_W,
    PLANE_B_H,
    build_bg_nametable_words,
    decompress_full_ojz_art,
    emit_bg_tile_blob,
    emit_zone_bg_layout,
    load_block_map,
    load_chunk_map,
    load_bg_layout,
)


class TestBgPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chunks = load_chunk_map(CHUNK_MAP_PATH)
        cls.blocks = load_block_map(BLOCK_MAP_PATH)
        cls.bg_layout = load_bg_layout(os.path.join(LAYOUT_DIR, "OJZ_1.bin"))
        cls.full_blob = decompress_full_ojz_art(OJZ_ART_PATH)

    def test_bg_layout_loaded(self):
        """OJZ_1.bin BG section is non-empty."""
        self.assertGreater(len(self.bg_layout), 0)
        self.assertGreater(len(self.bg_layout[0]), 0)

    def test_bg_nametable_size(self):
        """build_bg_nametable_words returns exactly 64×32 = 2048 words."""
        nt = build_bg_nametable_words(self.bg_layout, self.chunks, self.blocks)
        self.assertEqual(len(nt), PLANE_B_W * PLANE_B_H)

    def test_bg_tile_count_fits_capacity(self):
        """Deduped BG tile count must fit shared region capacity (512 slots)."""
        nt = build_bg_nametable_words(self.bg_layout, self.chunks, self.blocks)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "bg_tiles.bin")
            _, count = emit_bg_tile_blob(nt, self.full_blob, out_path)
            self.assertLessEqual(count, 512,
                                 f"BG tile count {count} exceeds shared region capacity 512")

    def test_bg_tile_blob_has_size_header(self):
        """First word of bg_tiles.bin is uncompressed body length (big-endian)."""
        nt = build_bg_nametable_words(self.bg_layout, self.chunks, self.blocks)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "bg_tiles.bin")
            _, count = emit_bg_tile_blob(nt, self.full_blob, out_path)
            with open(out_path, "rb") as f:
                data = f.read()
            header = struct.unpack(">H", data[:2])[0]
            body = data[2:]
            self.assertEqual(header, len(body))
            self.assertEqual(len(body), count * 32)

    def test_zone_bg_indices_in_shared_region(self):
        """Every emitted nametable word's tile_index ∈ [BG_TILE_BASE_SLOT, +cap)."""
        nt = build_bg_nametable_words(self.bg_layout, self.chunks, self.blocks)
        with tempfile.TemporaryDirectory() as tmpdir:
            tiles_path = os.path.join(tmpdir, "bg_tiles.bin")
            zone_path = os.path.join(tmpdir, "zone_bg.bin")
            src_to_canon, count = emit_bg_tile_blob(nt, self.full_blob, tiles_path)
            emit_zone_bg_layout(nt, src_to_canon, zone_path)
            with open(zone_path, "rb") as f:
                data = f.read()
            self.assertEqual(len(data), 64 * 32 * 2)
            for i in range(0, len(data), 2):
                word = struct.unpack(">H", data[i:i + 2])[0]
                tile_idx = word & 0x07FF
                self.assertGreaterEqual(
                    tile_idx, BG_TILE_BASE_SLOT,
                    f"BG word {i//2} tile_idx {tile_idx} below BG region base {BG_TILE_BASE_SLOT}")
                self.assertLess(
                    tile_idx, BG_TILE_BASE_SLOT + count,
                    f"BG word {i//2} tile_idx {tile_idx} above BG region top")

    def test_zone_bg_priority_bit_clear(self):
        """BG must stay low-priority — priority bit cleared on every word."""
        nt = build_bg_nametable_words(self.bg_layout, self.chunks, self.blocks)
        with tempfile.TemporaryDirectory() as tmpdir:
            tiles_path = os.path.join(tmpdir, "bg_tiles.bin")
            zone_path = os.path.join(tmpdir, "zone_bg.bin")
            src_to_canon, _ = emit_bg_tile_blob(nt, self.full_blob, tiles_path)
            emit_zone_bg_layout(nt, src_to_canon, zone_path)
            with open(zone_path, "rb") as f:
                data = f.read()
            for i in range(0, len(data), 2):
                word = struct.unpack(">H", data[i:i + 2])[0]
                self.assertEqual(word & 0x8000, 0,
                                 f"BG word {i//2} = 0x{word:04X} has priority bit set")


class TestBgAnimBandCeiling(unittest.TestCase):
    """BGANIM_MAX_BANDS is held by THREE independent authorities with no build-time
    guard until now — the gap the raster-substrate lens sweep booked (Tier 4 / B2,
    docs/superpowers/2026-08-18-raster-substrate-sweep-adjudication.md).

    The precedent is RASTER_MAX_PATCH, whose mirror in engine/ram.emp is a bare
    literal held to the real constant by a span `ensure` in raster.emp. That exact
    shape does NOT transfer here, and the difference is worth stating so nobody
    "upgrades" this gate into a vacuous one:

      * engine/ram.emp NAMES BGANIM_MAX_BANDS for BgAnim_LastStep's length rather
        than spelling a literal, so the array provably tracks constants.emp. An
        extern() span `ensure` would therefore compare constants.emp's value against
        an array sized BY constants.emp — it would measure itself and pass forever.
      * The two values that CAN drift are unreachable from any single .emp scope:
        bg_anim.emp's copy is module-local (not `pub`) and that file may not import
        engine.constants at all (it is lowered standalone by `bg_anim_port` against
        an empty symbol table), and the emitter's copy is Python.
      * The emitter's cap cannot be an .emp `ensure` even in principle: BgAnim_Table
        is a runtime-read binary blob assembled after engine code, so no comptime
        guard can see the band count it carries.

    So the guard lives where all three authorities are actually visible. What it
    preserves is the precedent's real property — compare independent restatements of
    one number and fail on disagreement — not its syntax.

    FAILURE MODE THIS CLOSES: raising the ceiling in the emitter alone let
    BgAnim_Update walk past BgAnim_LastStep. bg_anim.emp's `assert.w d7, ls,
    #BGANIM_MAX_BANDS` catches it in DEBUG only (asserts are zero bytes in the plain
    shape), so the release build had no defense at all.
    """

    AEON = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _emp_const(self, rel_path, name):
        from effects_budget_check import emp_constants, eval_int_expr
        path = os.path.join(self.AEON, rel_path)
        consts = emp_constants(path)
        self.assertIn(name, consts, f"{rel_path} no longer declares {name}")
        return eval_int_expr(consts[name], consts)

    def test_all_three_authorities_agree(self):
        engine = self._emp_const("engine/system/constants.emp", "BGANIM_MAX_BANDS")
        local = self._emp_const("engine/level/bg_anim.emp", "BGANIM_MAX_BANDS")
        from inject_editor_bg import BGANIM_MAX_BANDS as emitter

        self.assertEqual(
            engine, local,
            f"engine/system/constants.emp says BGANIM_MAX_BANDS={engine} but "
            f"engine/level/bg_anim.emp's module-local mirror says {local}. The first "
            f"sizes engine/ram.emp's BgAnim_LastStep; the second bounds "
            f"BgAnim_Update's runtime assert. If the mirror is the LARGER, the assert "
            f"lets a table through that overruns the array.")
        self.assertEqual(
            engine, emitter,
            f"engine/system/constants.emp says BGANIM_MAX_BANDS={engine} but "
            f"tools/inject_editor_bg.py caps bands at {emitter}. The emitter's cap is "
            f"the RELEASE defense for BgAnim_Update's walk (the .emp assert is "
            f"DEBUG-only), so an emitter ceiling above the array's real width writes a "
            f"table that walks off BgAnim_LastStep with nothing to catch it.")

    def test_ram_array_still_names_the_constant(self):
        """The reasoning above depends on ram.emp NAMING BGANIM_MAX_BANDS rather than
        spelling a literal. If that ever changes, BgAnim_LastStep becomes a fourth
        independent authority this gate does not read — so fail here and make whoever
        changed it widen the gate."""
        path = os.path.join(self.AEON, "engine", "ram.emp")
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.lstrip().startswith("BgAnim_LastStep:"):
                    self.assertIn(
                        "BGANIM_MAX_BANDS", line,
                        "engine/ram.emp's BgAnim_LastStep no longer sizes itself from "
                        "BGANIM_MAX_BANDS. It is now an independent restatement of the "
                        "band ceiling, and TestBgAnimBandCeiling does not read it — "
                        "either restore the name or add the array's real width to the "
                        "comparison above (see RASTER_STATE_SIZE in "
                        "engine/effects/raster.emp for the span-guard shape that fits "
                        "a literal).")
                    return
        self.fail("engine/ram.emp declares no BgAnim_LastStep field")


if __name__ == "__main__":
    unittest.main()
