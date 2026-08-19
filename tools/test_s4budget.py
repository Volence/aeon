#!/usr/bin/env python3
"""Tests for s4budget — the ROM/RAM/VRAM budget dashboard.

REWRITTEN 2026-08-18 alongside the parser, and the reason is the point of the
file. The previous 40 tests were green for the entire life of a parser that read
NOTHING out of a real listing: every fixture was hand-authored with AS Macro
Assembler page headers, so fixture and parser were co-designed and the suite
could only ever confirm the parser's own assumptions (tools lens sweep D7).

So this suite is built the other way round:

  * The fixtures are CUT FROM REAL BUILDS. `tools/fixtures/*.lst` are excerpts of
    actual `sigil build --emit-lst` output (see fixtures/make_listing_excerpt.py)
    — every listing line is byte-identical to one a build produced. Nothing here
    hand-writes a listing.
  * The map and VRAM fixtures are the REAL, tracked `games/sonic4/map.toml` and
    `games/sonic4/vram.toml`, not miniatures.
  * Every expected number is DERIVED from the fixture inside the test (or
    computed in a comment from addresses visible in it), never copied off a
    neighbouring pin.
  * Poison cases are MUTATIONS of the real fixture — delete the header, break a
    row, contradict the trailer — each asserting the parser fails LOUDLY. The
    D7 failure was silence, so silence is what the poisons hunt.

The one thing this suite must never allow back: an unreadable listing rendering
as a number. `test_the_D7_string_is_unreachable` is that assertion, by name.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from s4budget import (  # noqa: E402
    ListingFormatError,
    compute_ram_layout,
    format_summary,
    load_map,
    load_vram_layout,
    main as s4budget_main,
    parse_listing,
    ram_labels,
    read_system_stack,
    resolve_budgets,
    rom_labels,
)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
S4_LST = os.path.join(HERE, "fixtures", "s4_listing_excerpt.lst")
DEMO_LST = os.path.join(HERE, "fixtures", "demo_listing_excerpt.lst")
S4_MAP = os.path.join(REPO, "games", "sonic4", "map.toml")
DEMO_MAP = os.path.join(REPO, "games", "demo", "map.toml")


def read(path):
    with open(path) as f:
        return f.readlines()


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = s4budget_main(argv)
    return code, out.getvalue(), err.getvalue()


@contextlib.contextmanager
def temp_text(text, suffix=".lst"):
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    try:
        yield path
    finally:
        os.unlink(path)


@contextlib.contextmanager
def temp_rom(size):
    fd, path = tempfile.mkstemp(suffix=".bin")
    with os.fdopen(fd, "wb") as f:
        f.write(b"\x00" * size)
    try:
        yield path
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# Parsing a real listing
# ---------------------------------------------------------------------------

class TestRealListing(unittest.TestCase):
    def setUp(self):
        self.listing = parse_listing(read(S4_LST))

    def test_symbol_count_matches_the_listings_own_trailer(self):
        text = open(S4_LST).read()
        declared = int(next(l for l in text.splitlines()
                            if l.strip().endswith("symbols")
                            and "unused" not in l).split()[0])
        self.assertEqual(self.listing.declared_count, declared)
        self.assertEqual(len(self.listing.symbols), declared)

    def test_addresses_come_out_as_the_listing_wrote_them(self):
        by = self.listing.by_name
        self.assertEqual(by["Vectors"], 0x0)
        self.assertEqual(by["EntryPoint"], 0x200)
        self.assertEqual(by["DeformTable_Zero"], 0x11984)
        self.assertEqual(by["EndOfRom"], 0xA11C0)
        self.assertEqual(by["Tile_Cache_Nametable"], 0xFFFF0000)
        self.assertEqual(by["Game_RAM_End"], 0xFFFFBC02)

    def test_rom_and_ram_split_exhaust_the_symbol_set(self):
        """No symbol may fall between the buckets and vanish silently.

        The old parser dropped every RAM symbol exactly this way: it required an
        `FFFFFFFFFFFF` sign-extended prefix that sigil does not emit, so RAM
        labels matched neither the RAM test nor the `< $400000` ROM test and were
        discarded without a word.
        """
        rom, ram = rom_labels(self.listing), ram_labels(self.listing)
        self.assertEqual(len(rom) + len(ram), len(self.listing.symbols))
        self.assertEqual(set(rom) & set(ram), set())
        self.assertGreater(len(ram), 0, "a real build always has RAM symbols")

    def test_every_symbol_is_type_C(self):
        """Sigil emits no absolute symbols. The old VRAM report read only those,
        which is why it silently produced nothing on every real build."""
        self.assertEqual({s.kind for s in self.listing.symbols}, {"C"})

    def test_the_demo_listing_parses_too(self):
        """A second real build, from a different game — the format is the format."""
        demo = parse_listing(read(DEMO_LST))
        self.assertGreater(demo.declared_count, 0)
        self.assertIn("EndOfRom", demo.by_name)
        self.assertIn("ObjDef_DemoBox", demo.by_name)


# ---------------------------------------------------------------------------
# Poisons — every one a MUTATION of the real fixture
# ---------------------------------------------------------------------------

class TestPoison(unittest.TestCase):
    def setUp(self):
        self.text = open(S4_LST).read()
        self.lines = self.text.splitlines(keepends=True)

    def _expect_error(self, lines, needle):
        with self.assertRaises(ListingFormatError) as cm:
            parse_listing(lines)
        self.assertIn(needle, str(cm.exception).lower())

    def test_an_AS_era_listing_is_refused(self):
        """The exact input that produced zeros for months.

        Real AS listing shape: a page header, then `addr: bytes  source`. It has
        no sigil symbol table, so it must stop the tool dead rather than yield an
        empty model.
        """
        as_lst = [
            "AS V1.42 Beta [Bld 139] - source file s4.asm - page 1 - 8/18/2026\n",
            "\n",
            "       1/000000 : 4E71                nop\n",
            "       2/000002 : 4E75                rts\n",
        ]
        self._expect_error(as_lst, "symbol table")

    def test_a_missing_symbol_table_header_is_refused(self):
        self._expect_error([l for l in self.lines if "Symbol Table" not in l],
                           "symbol table")

    def test_a_missing_count_trailer_is_refused(self):
        """Without the trailer there is nothing to catch a partial parse against."""
        self._expect_error(
            [l for l in self.lines if not l.strip().endswith("symbols")
             or "unused" in l],
            "trailer")

    def test_a_trailer_that_contradicts_the_rows_is_refused(self):
        """The check that would have caught D7 on day one.

        Claim one more symbol than the file carries: the parser must notice that
        its own harvest is short, rather than reporting on what it managed to get.
        """
        n = len(parse_listing(self.lines).symbols)
        poisoned = [l.replace(f"   {n} symbols", f"   {n + 1} symbols")
                    if l.strip() == f"{n} symbols" else l for l in self.lines]
        self._expect_error(poisoned, "incomplete")

    def test_a_row_the_parser_cannot_read_is_refused(self):
        """One unreadable row must fail the file, not shrink the model by one."""
        poisoned = [l.replace(" EndOfRom : A11C0 C |", " EndOfRom = A11C0 C |")
                    for l in self.lines]
        self._expect_error(poisoned, "incomplete")

    def test_a_dropped_source_row_is_refused(self):
        """The two halves are one table; losing a row from either is a defect."""
        poisoned = [l for l in self.lines
                    if not l.startswith("(0) 1897/A11C0 :")]
        self._expect_error(poisoned, "source-listing parse is incomplete")

    def test_halves_that_disagree_on_a_value_are_refused(self):
        """Same symbol, two addresses — one of the two regexes is misreading."""
        poisoned = [l.replace(" EndOfRom : A11C0 C |", " EndOfRom : B11C0 C |")
                    for l in self.lines]
        self._expect_error(poisoned, "disagree")

    def test_an_empty_file_is_refused(self):
        self._expect_error([], "symbol table")

    def test_a_zero_symbol_listing_is_refused(self):
        self._expect_error(
            ["  Symbol Table (* = unused):\n", "\n",
             "   0 symbols\n", "    0 unused symbols\n"],
            "0 symbols")


# ---------------------------------------------------------------------------
# RAM — the axis the dead parser lost entirely
# ---------------------------------------------------------------------------

class TestRAM(unittest.TestCase):
    def setUp(self):
        self.listing = parse_listing(read(S4_LST))
        self.ram = ram_labels(self.listing)
        self.layout = compute_ram_layout(self.ram, 0xFFFFFF00)

    def test_lower_ram_buffers_are_sized_by_the_gap_to_their_successor(self):
        """Derived from the fixture's own addresses, not from a pin.

        Tile_Cache_Nametable $FFFF0000 -> Tile_Cache_Collision $FFFF2580 is
        $2580 = 9600 bytes; Block_Stage_Buffers $FFFF3842 -> Page_Table $FFFF6842
        is $3000 = 12288.
        """
        sizes = {e.name: e.size for e in self.layout.lower}
        self.assertEqual(sizes["Tile_Cache_Nametable"],
                         self.ram["Tile_Cache_Collision"] - self.ram["Tile_Cache_Nametable"])
        self.assertEqual(sizes["Tile_Cache_Nametable"], 9600)
        self.assertEqual(sizes["Block_Stage_Buffers"], 0x3000)
        # The last lower entry runs to the $FFFF8000 boundary, not to the stack.
        self.assertEqual(sizes["Lower_RAM_End"], 0xFFFF8000 - self.ram["Lower_RAM_End"])

    def test_span_and_free_are_measured_against_the_top_allocation(self):
        top = max(self.ram.values())
        self.assertEqual(top, 0xFFFFBC02)                    # Game_RAM_End
        self.assertEqual(self.layout.span_used, top - 0xFFFF0000)
        self.assertEqual(self.layout.free_before_stack, 0xFFFFFF00 - top)

    def test_two_labels_at_one_address_do_not_become_a_buffer(self):
        """Cheat_Flags and Engine_RAM_End share $FFFFB836 in the real build."""
        self.assertEqual(self.ram["Cheat_Flags"], self.ram["Engine_RAM_End"])
        self.assertNotIn("Cheat_Flags", {e.name for e in self.layout.upper})

    def test_no_ram_symbols_yields_None_not_a_zeroed_layout(self):
        """A zeroed layout is indistinguishable from a dead parser. None is not."""
        self.assertIsNone(compute_ram_layout({}, 0xFFFFFF00))

    def test_the_stack_address_is_read_from_the_engine_source(self):
        """Not restated here: SYSTEM_STACK is a `pub const` that can move."""
        value, derived = read_system_stack(REPO)
        self.assertTrue(derived, "SYSTEM_STACK not found in engine/system/constants.emp")
        with open(os.path.join(REPO, "engine", "system", "constants.emp")) as f:
            src = f.read()
        self.assertIn(f"SYSTEM_STACK = ${value:X}", src)


# ---------------------------------------------------------------------------
# Budgets — from the real map.toml
# ---------------------------------------------------------------------------

class TestBudgets(unittest.TestCase):
    def test_the_real_map_declares_the_object_bank_budget(self):
        model = load_map(S4_MAP)
        region = model.region("object_bank")
        self.assertIsNotNone(region)
        budget = next(b for b in model.budgets if b.region == "object_bank")
        self.assertEqual(budget.cursor, "DeformTable_Zero")
        self.assertEqual(budget.ceiling, 0x20000)
        self.assertEqual(region.lma_base, 0x10000)

    def test_the_cursor_resolves_against_the_listing(self):
        model = load_map(S4_MAP)
        listing = parse_listing(read(S4_LST))
        rows, unresolved = resolve_budgets(model, listing)
        self.assertEqual(unresolved, [])
        row = next(r for r in rows if r.region == "object_bank")
        # Derived: cursor $11984 - base $10000 = $1984; limit $20000 - $10000.
        self.assertEqual(row.used, listing.by_name["DeformTable_Zero"] - 0x10000)
        self.assertEqual(row.used, 0x1984)
        self.assertEqual(row.limit, 0x10000)
        self.assertFalse(row.breached)

    def test_an_unresolvable_cursor_is_reported_by_name_not_dropped(self):
        """'No row' and '0 bytes used' must not look the same.

        The demo listing has no DeformTable_Zero, so sonic4's map against it is
        exactly the vanished-cursor case.
        """
        rows, unresolved = resolve_budgets(load_map(S4_MAP), parse_listing(read(DEMO_LST)))
        self.assertEqual(rows, [])
        self.assertEqual(len(unresolved), 1)
        self.assertIn("DeformTable_Zero", unresolved[0])

    def test_each_game_resolves_its_own_cursor(self):
        rows, unresolved = resolve_budgets(load_map(DEMO_MAP), parse_listing(read(DEMO_LST)))
        self.assertEqual(unresolved, [])
        self.assertEqual(rows[0].cursor_name, "ObjDef_DemoBox")

    def test_a_map_with_no_regions_is_refused(self):
        with temp_text('[[budget]]\nregion="x"\nceiling=1\ncursor="y"\n', ".toml") as p:
            with self.assertRaises(ListingFormatError):
                load_map(p)


# ---------------------------------------------------------------------------
# VRAM — from the real vram.toml, with UNION occupancy
# ---------------------------------------------------------------------------

class TestVRAM(unittest.TestCase):
    def test_occupancy_is_the_union_and_agrees_with_the_declared_free_list(self):
        """Two independently-authored numbers in vram.toml must agree.

        The regions imply an occupancy; the [[free]] blocks state one. Summing
        region tile counts instead of unioning them reports 2129 of 2048 tiles
        (104%) for a correct map, because window_plane deliberately aliases the
        tail of plane_b.
        """
        v = load_vram_layout("sonic4")
        self.assertIsNotNone(v)
        self.assertEqual(v.occupied_tiles + v.free_tiles, v.total_tiles)
        self.assertEqual(v.free_tiles, v.declared_free_tiles)
        self.assertLess(v.occupied_tiles, v.total_tiles)
        # The naive sum overcounts precisely because of the declared overlay, and
        # by enough to cross 100% — which is what makes it worth testing.
        naive = sum(r.tiles for r in v.regions)
        self.assertGreater(naive, v.occupied_tiles)
        self.assertGreater(naive, v.total_tiles)

    def test_the_plane_b_overlay_is_reported_as_declared(self):
        v = load_vram_layout("sonic4")
        self.assertTrue(any("declared overlay" in o for o in v.overlaps))
        self.assertFalse(any("UNDECLARED" in o for o in v.overlaps),
                         f"undeclared VRAM overlap: {v.overlaps}")

    def test_an_unknown_game_is_unmeasured_not_invented(self):
        self.assertIsNone(load_vram_layout("no-such-game"))
        self.assertIsNone(load_vram_layout(None))


# ---------------------------------------------------------------------------
# End to end: gating, and the D7 string
# ---------------------------------------------------------------------------

class TestCLI(unittest.TestCase):
    def test_summary_on_real_inputs_measures_every_axis(self):
        with temp_rom(0xA11C0) as rom:
            code, out, err = run_main([S4_LST, rom, "--map", S4_MAP, "--summary"])
        self.assertEqual(code, 0, err)
        self.assertEqual(out, "")
        self.assertNotIn("UNMEASURED", err)
        for axis in ("ROM:", "object_bank:", "RAM:", "Free:"):
            self.assertIn(axis, err)

    def test_the_D7_string_is_unreachable(self):
        """`RAM: 0KB/64KB (0%)` was a dead parser wearing a measurement's clothes.

        Neither a real build nor a broken listing may produce a zero-valued axis:
        the real one carries a number, the broken one stops the tool.
        """
        with temp_rom(0xA11C0) as rom:
            _c, _o, err = run_main([S4_LST, rom, "--map", S4_MAP, "--summary"])
        self.assertNotIn("0KB/64KB", err)
        self.assertNotIn("(0%)", err)

        with temp_text("nothing resembling a listing\n") as lst, temp_rom(16) as rom:
            code, out, err = run_main([lst, rom, "--map", S4_MAP, "--summary"])
        self.assertEqual(code, 1)
        self.assertIn("cannot read", err)
        self.assertEqual(out, "")
        # No summary line at all. Matched on the ` | ` separator rather than on
        # "RAM:", because the refusal diagnostic deliberately QUOTES the old
        # string to explain itself — and a substring test would have caught the
        # explanation instead of the defect.
        self.assertNotIn(" | ", err)

    def test_no_map_says_UNMEASURED_and_still_reports_the_real_axes(self):
        with temp_rom(0xA11C0) as rom:
            code, _o, err = run_main([S4_LST, rom, "--summary"])
        self.assertEqual(code, 0)
        self.assertIn("budgets: UNMEASURED", err)
        self.assertIn("RAM:", err)

    def test_a_map_path_that_does_not_exist_is_an_error_not_a_downgrade(self):
        """A typo must not silently turn the budget gate into a warning."""
        with temp_rom(16) as rom:
            code, _o, err = run_main([S4_LST, rom, "--map", "/nope/map.toml", "--summary"])
        self.assertEqual(code, 1)
        self.assertIn("map file not found", err)

    def test_a_real_object_bank_breach_fails_the_build(self):
        """Ceiling lowered under the real cursor; everything else untouched."""
        with open(S4_MAP) as f:
            doc = f.read()
        # $11000 sits below the fixture's real cursor at $11984.
        breach_map = doc.replace("ceiling = 0x20000", "ceiling = 0x11000")
        self.assertNotEqual(breach_map, doc)
        with temp_text(breach_map, ".toml") as mp, temp_rom(0xA11C0) as rom:
            code, _o, err = run_main([S4_LST, rom, "--map", mp, "--summary"])
        self.assertEqual(code, 1)
        self.assertIn("BUDGET EXCEEDED", err)
        self.assertIn("DeformTable_Zero", err)

    def test_a_rom_over_its_declared_region_size_fails_the_build(self):
        with open(S4_MAP) as f:
            small = f.read().replace("size = 0x400000", "size = 0x1000", 1)
        with temp_text(small, ".toml") as mp, temp_rom(0x2000) as rom:
            code, _o, err = run_main([S4_LST, rom, "--map", mp, "--summary"])
        self.assertEqual(code, 1)
        self.assertIn("BUDGET EXCEEDED", err)
        self.assertIn("ROM", err)

    def test_ram_reaching_the_stack_fails_the_build(self):
        """The one budget with no other enforcer.

        sigil gates the map's ROM ceilings at pack time; nothing gates RAM growing
        into the stack. Built by moving one real symbol in the real fixture.
        """
        poisoned = open(S4_LST).read().replace("FFFFBC02", "FFFFFFF8")
        with temp_text(poisoned) as lst, temp_rom(0xA11C0) as rom:
            code, _o, err = run_main([lst, rom, "--map", S4_MAP, "--summary"])
        self.assertEqual(code, 1)
        self.assertIn("reached the stack", err)

    def test_full_report_and_json_carry_the_same_measurements(self):
        with temp_rom(0xA11C0) as rom:
            code, text, _e = run_main([S4_LST, rom, "--map", S4_MAP])
            self.assertEqual(code, 0)
            code, js, _e = run_main([S4_LST, rom, "--map", S4_MAP, "--json"])
        self.assertEqual(code, 0)
        for heading in ("=== ROM Budget ===", "=== RAM Budget ===", "=== VRAM Budget ==="):
            self.assertIn(heading, text)
        data = json.loads(js)
        self.assertEqual(data["rom"]["budgets"][0]["used"], 0x1984)
        self.assertEqual(data["ram"]["span_used"], 0xBC02)
        self.assertEqual(data["vram"]["occupied_tiles"] + data["vram"]["free_tiles"], 2048)
        self.assertEqual(data["listing"]["symbols"], len(parse_listing(read(S4_LST)).symbols))

    def test_a_missing_listing_exits_one(self):
        code, _o, err = run_main(["/nonexistent.lst", "/nonexistent.bin"])
        self.assertEqual(code, 1)
        self.assertIn("not found", err)

    def test_summary_says_UNMEASURED_when_the_rom_binary_is_absent(self):
        code, _o, err = run_main([S4_LST, "/nonexistent.bin", "--map", S4_MAP, "--summary"])
        self.assertEqual(code, 0)
        self.assertIn("ROM: UNMEASURED", err)


class TestSummaryFormatting(unittest.TestCase):
    def test_a_small_but_real_budget_never_renders_as_zero(self):
        """demo's object bank really is a few bytes. `0KB/64KB` would be a lie
        in the same words as the D7 defect."""
        listing = parse_listing(read(DEMO_LST))
        rows, _ = resolve_budgets(load_map(DEMO_MAP), listing)
        line = format_summary(96451, 0x400000, rows, [],
                              compute_ram_layout(ram_labels(listing), 0xFFFFFF00))
        self.assertIn("object_bank:", line)
        self.assertNotIn("0KB/64KB", line)
        self.assertNotIn("UNMEASURED", line)

    def test_absent_axes_say_the_word_instead_of_a_number(self):
        line = format_summary(None, 0x400000, [], ["object_bank (cursor gone)"], None)
        self.assertIn("ROM: UNMEASURED", line)
        self.assertIn("RAM: UNMEASURED", line)
        self.assertIn("object_bank: UNMEASURED", line)
        self.assertNotIn("(0%)", line)
        self.assertNotIn("0KB", line)


if __name__ == "__main__":
    unittest.main()
