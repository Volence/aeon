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


def make_anim_table(bodies):
    """Build an `offsets`-construct animation table from a list of body byte
    strings, laid out exactly as sigil emits one: a word offset per entry from
    the table base, then the bodies packed inline behind it."""
    table, blob, off = [], b"", len(bodies) * 2
    for b in bodies:
        table.append(off)
        blob += bytes(b)
        off += len(b)
    return b"".join(struct.pack(">H", o) for o in table) + blob


#: The control-code values, spelled here so the walk tests do not depend on the
#: tree's constants file being present. `TestOpcodeDerivation` is what binds
#: these to the tree — if engine/system/constants.emp renumbers a code, that test
#: fails, not these.
AF_END, AF_BACK, AF_CHANGE = 0xFF, 0xFE, 0xFD
AF_ROUTINE, AF_DELETE, AF_CALLBACK = 0xFC, 0xFB, 0xFA
AF_SOUND, AF_COLLISION, AF_SET_FIELD = 0xF9, 0xF8, 0xF7
AF = {"AF_END": AF_END, "AF_BACK": AF_BACK, "AF_CHANGE": AF_CHANGE,
      "AF_ROUTINE": AF_ROUTINE, "AF_DELETE": AF_DELETE, "AF_CALLBACK": AF_CALLBACK,
      "AF_SOUND": AF_SOUND, "AF_COLLISION": AF_COLLISION, "AF_SET_FIELD": AF_SET_FIELD}
EVENTS = {AF_CALLBACK: 4, AF_SOUND: 2, AF_COLLISION: 2, AF_SET_FIELD: 4}
MAPFRAME_OFF = 0x23


class TestAnimWalk(unittest.TestCase):
    """The script walk, over hand-built tables.

    The expectations are read off the format in engine/objects/animate.emp's
    header: byte 0 is a DURATION, bytes 0-$F6 are frame indices, and every
    control code's operand is its own kind of thing — a rewind COUNT, an anim
    ID, a sound id — never a frame.
    """

    def walk(self, bodies, count=None):
        blob = make_anim_table(bodies)
        return D.parse_anim_table(blob, 0, count if count is not None else len(bodies),
                                  "t", AF, EVENTS, MAPFRAME_OFF)

    def test_the_duration_byte_is_not_a_frame(self):
        by_id, _ = self.walk([[7, 0x40, 0x41, AF_END]])
        self.assertEqual(by_id[0], {0x40, 0x41},
                         "byte 0 is the hold, not the first frame")

    def test_af_back_operand_is_a_count_not_a_frame(self):
        # `[5, $C3, $C4, AF_BACK, 1]` holds the last pose. The trailing 1 is a
        # rewind count; a walker that treated it as a frame would invent frame 1.
        by_id, _ = self.walk([[5, 0xC3, 0xC4, AF_BACK, 1]])
        self.assertEqual(by_id[0], {0xC3, 0xC4})

    def test_af_change_operand_is_an_anim_id_not_a_frame(self):
        by_id, _ = self.walk([[5, 0x30, AF_CHANGE, 9], [5, 0x31, AF_END]])
        self.assertEqual(by_id[0], {0x30}, "the 9 is the id of animation 1, not frame 9")
        self.assertEqual(by_id[1], {0x31})

    def test_inline_events_are_read_through_and_their_operands_skipped(self):
        # AF_SOUND takes one operand byte; the interpreter continues at the byte
        # after it. Pick operands that WOULD look like frames if mis-read.
        by_id, _ = self.walk([[3, 0x20, AF_SOUND, 0x55, 0x21, AF_END]])
        self.assertEqual(by_id[0], {0x20, 0x21}, "$55 is a sound id, not a frame")
        by_id, _ = self.walk([[3, 0x20, AF_COLLISION, 0x66, 0x21, AF_END]])
        self.assertEqual(by_id[0], {0x20, 0x21})
        by_id, _ = self.walk([[3, 0x20, AF_CALLBACK, 0x12, 0x34, 0, 0x21, AF_END]])
        self.assertEqual(by_id[0], {0x20, 0x21}, "the callback target is an address pair")

    def test_af_set_field_targeting_mapping_frame_contributes_its_value(self):
        # DEBUG asserts a script cannot do this; release does not. If one ever
        # does, the value IS a displayed frame and must not be lost.
        by_id, notes = self.walk([[3, 0x20, AF_SET_FIELD, MAPFRAME_OFF, 0x7E, 0, AF_END]])
        self.assertIn(0x7E, by_id[0])
        self.assertTrue(any("AF_SET_FIELD" in n for n in notes), "and it says so")

    def test_af_set_field_targeting_another_byte_contributes_nothing(self):
        by_id, notes = self.walk([[3, 0x20, AF_SET_FIELD, MAPFRAME_OFF + 1, 0x7E, 0, AF_END]])
        self.assertEqual(by_id[0], {0x20})
        self.assertEqual(notes, [])

    def test_every_terminator_stops_the_walk(self):
        for term in (AF_END, AF_ROUTINE, AF_DELETE):
            by_id, _ = self.walk([[3, 0x20, term], [3, 0x21, AF_END]])
            self.assertEqual(by_id[0], {0x20}, f"${term:02X} terminates")

    def test_an_underflowing_rewind_is_unmeasurable_not_silently_truncated(self):
        # `.cc_back` subtracts with a byte `sub.b`, so a rewind bigger than the
        # cursor wraps and the interpreter reads outside the body. Stopping the
        # walk there would silently narrow the reachable set.
        with self.assertRaises(D.Unmeasurable):
            self.walk([[5, 0xC3, 0xC4, AF_BACK, 9], [5, 0x31, AF_END]])

    def test_a_rewind_within_the_cursor_is_fine(self):
        by_id, _ = self.walk([[5, 0xC3, 0xC4, AF_BACK, 2], [5, 0x31, AF_END]])
        self.assertEqual(by_id[0], {0xC3, 0xC4})

    def test_a_body_with_no_terminator_is_unmeasurable(self):
        with self.assertRaises(D.Unmeasurable):
            self.walk([[3] + [0x20] * 8, [3, 0x21, AF_END]])

    def test_a_count_that_disagrees_with_anim_count_is_unmeasurable(self):
        with self.assertRaises(D.Unmeasurable):
            self.walk([[3, 0x20, AF_END], [3, 0x21, AF_END]], count=3)

    def test_a_non_table_head_is_unmeasurable_not_empty(self):
        with self.assertRaises(D.Unmeasurable):
            D.parse_anim_table(b"\x00\x00\x00\x00", 0, 2, "t", AF, EVENTS, MAPFRAME_OFF)
        with self.assertRaises(D.Unmeasurable):
            D.parse_anim_table(b"\x00\x03\x00\x00", 0, 1, "t", AF, EVENTS, MAPFRAME_OFF)


class TestOpcodeDerivation(unittest.TestCase):
    """The walk's opcode classification is DERIVED from AnimateSprite, so this
    checks the shape of what came back, not numbers copied out of a run."""

    def setUp(self):
        self.values, self.events, self.threshold = D.anim_opcodes()

    def test_the_hand_written_test_codes_match_the_tree(self):
        self.assertEqual(self.values, AF, "the codes the walk tests use are the tree's")

    def test_terminators_are_not_events(self):
        for name in ("AF_END", "AF_BACK", "AF_CHANGE", "AF_ROUTINE", "AF_DELETE"):
            self.assertNotIn(self.values[name], self.events,
                             f"{name} ends the walk; it has no inline width")

    def test_events_are_events(self):
        for name in ("AF_CALLBACK", "AF_SOUND", "AF_COLLISION", "AF_SET_FIELD"):
            self.assertIn(self.values[name], self.events,
                          f"{name} is read THROUGH — the interpreter advances past it")

    def test_every_event_width_is_even_and_at_least_two(self):
        # animate.emp's header states the invariant: "All events consume an even
        # number of bytes." An odd width would desynchronise every later frame.
        for code, w in self.events.items():
            self.assertGreaterEqual(w, 2, f"${code:02X} must consume its opcode plus operands")
            self.assertEqual(w % 2, 0, f"${code:02X} breaks the even-width format invariant")

    def test_the_threshold_is_the_lowest_control_code(self):
        self.assertEqual(self.threshold, min(self.values.values()))


class TestTiltExpansion(unittest.TestCase):
    """The tilt banks, against the sheet geometry player_common.emp's own
    `ensure` pins: the four WALK blocks tile TILT_WALK_BASE up to where the RUN
    blocks begin, and the four RUN blocks follow them."""

    def test_the_walk_cycle_expands_to_fill_the_walk_blocks(self):
        P = "games/sonic4/player/player_common.emp"
        base = D.local_const(P, "TILT_WALK_BASE")
        length = D.local_const(P, "TILT_WALK_LEN")
        run_base = D.local_const(P, "TILT_RUN_BASE")
        walk_cycle = set(range(base, base + length))
        got, _ = D.tilt_expansion({0: walk_cycle, 1: set()})
        self.assertEqual(got, set(range(base, run_base)),
                         "four blocks of the walk cycle tile the span up to the run blocks")

    def test_the_run_cycle_expands_to_fill_the_run_blocks(self):
        P = "games/sonic4/player/player_common.emp"
        base = D.local_const(P, "TILT_RUN_BASE")
        length = D.local_const(P, "TILT_RUN_LEN")
        sets = D.local_const(P, "TILT_SETS")
        got, _ = D.tilt_expansion({0: set(), 1: set(range(base, base + length))})
        self.assertEqual(got, set(range(base, base + sets * length)))

    def test_an_untilted_animation_expands_to_nothing(self):
        got, _ = D.tilt_expansion({5: {0x9B, 0x9C}})
        self.assertEqual(got, set(), "only WALK and RUN have tilted art behind them")


class TestAppendageBank(unittest.TestCase):
    def test_the_roll_cycle_expands_by_the_masked_banks(self):
        roll = D.const_from_emp("games/sonic4/config/constants.emp", "ANIM_ROLL")
        got, note = D.appendage_bank({roll: {5}})
        # The banks are the submasks of the `andi.b` mask, so the expansion of a
        # single frame is one frame per bank and they are all distinct.
        self.assertIn(5, got)
        self.assertEqual(len(got), note.count("/") + 1)

    def test_a_non_roll_animation_does_not_bank(self):
        roll = D.const_from_emp("games/sonic4/config/constants.emp", "ANIM_ROLL")
        got, _ = D.appendage_bank({roll + 1: {5}})
        self.assertEqual(got, set())


class TestClimbFrames(unittest.TestCase):
    def test_the_cycle_is_the_inclusive_span_between_its_bounds(self):
        P = "games/sonic4/player/player_climb.emp"
        lo = D.local_const(P, "CLIMB_FRAME_LO")
        hi = D.local_const(P, "CLIMB_FRAME_HI")
        self.assertEqual(D.climb_frames()["cycle"], set(range(lo, hi + 1)))

    def test_one_clamber_pose_per_four_byte_entry(self):
        P = "games/sonic4/player/player_climb.emp"
        total = D.local_const(P, "CLIMB_CLAMBER_BYTES")
        self.assertEqual(len(D.climb_frames()["clamber"]), total // 4,
                         "the cursor advances by 4, so entry 0 of each 4 is the frame")


class TestWriteSiteScan(unittest.TestCase):
    """The scanner has to find writers the tree spells in more than one way."""

    def setUp(self):
        self.sites = D.scan_write_sites()
        self.keys = {(p, s) for p, _, s, _ in self.sites}

    def test_it_finds_the_script_interpreter(self):
        self.assertIn(("engine/objects/animate.emp", "AnimateSprite"), self.keys)

    def test_it_finds_the_unnamed_sized_overlay_writer(self):
        # Load_Object initialises prev_anim..prev_frame with one `move.l` over a
        # `:l` sized override — the line never says "mapping_frame", but it
        # writes it, and it runs for EVERY spawned object. A name-only scan
        # misses the one writer with the widest reach in the tree.
        self.assertIn(("engine/objects/load_object.emp", "Load_Object"), self.keys)

    def test_every_site_found_is_claimed_by_a_writers_entry(self):
        unclaimed = sorted(self.keys - set(D.WRITERS))
        self.assertEqual(unclaimed, [], "an unclassified writer widens the reachable set")

    def test_every_writers_entry_still_names_a_live_site(self):
        stale = sorted(set(D.WRITERS) - self.keys)
        self.assertEqual(stale, [], "a claim whose routine moved is a claim about nothing")

    def test_the_claimed_site_counts_match(self):
        counts = {}
        for p, _, s, _ in self.sites:
            counts[(p, s)] = counts.get((p, s), 0) + 1
        for key, spec in D.WRITERS.items():
            self.assertEqual(counts.get(key), spec["sites"],
                             f"{key} holds a different number of writes than it claims")

    def test_comment_only_mentions_are_not_sites(self):
        self.assertEqual(D._strip_comment("        move.b  d0, mapping_frame(a0) // x").strip(),
                         "move.b  d0, mapping_frame(a0)")
        self.assertEqual(D._strip_comment("// move.b d0, mapping_frame(a0)").strip(), "")


class TestSubjectBindings(unittest.TestCase):
    def test_every_subject_is_bound_by_a_record_that_names_all_three_labels(self):
        bind = D.subject_bindings()
        for _, art, dplc, *_ in D.SUBJECTS:
            self.assertIn(art, bind, f"{art} is bound by no record")
            self.assertEqual(bind[art]["dplc"], dplc,
                             f"{art}'s record pairs it with a different DPLC table")
            self.assertTrue(bind[art]["anim"].startswith("Ani_"))

    def test_no_routine_animates_one_character_against_another_s_dplc(self):
        self.assertEqual(D.check_anim_dplc_pairings(), [])

    def test_every_ability_gated_writer_has_exactly_one_owner(self):
        """A writer routed to one character because only that character's hook
        can reach it is only correct while the hook has ONE owner."""
        bind = D.subject_bindings()
        for key, spec in D.WRITERS.items():
            if not spec.get("ability"):
                continue
            owner = D.sole_ability_owner(bind, spec["ability"])
            self.assertIsNotNone(owner, f"{key} routes on {spec['ability']}, which zero or "
                                        f"several records own")
            self.assertEqual(bind[owner]["kind"], "player")
            expected = next(a for n, a, *_ in D.SUBJECTS if n == spec["art"])
            self.assertEqual(owner, expected,
                             f"{key} routes to {spec['art']} but {spec['ability']} belongs to "
                             f"{owner}")

    def test_a_second_owner_of_the_hook_breaks_the_sole_owner_check(self):
        bind = D.subject_bindings()
        ability = next(s["ability"] for s in D.WRITERS.values() if s.get("ability"))
        self.assertIsNotNone(D.sole_ability_owner(bind, ability))
        forged = dict(bind)
        victim = next(a for a, b in forged.items() if b.get("ability") != ability)
        forged[victim] = dict(forged[victim], ability=ability)
        self.assertIsNone(D.sole_ability_owner(forged, ability),
                          "two owners must read as undetermined, not as the first one")


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
