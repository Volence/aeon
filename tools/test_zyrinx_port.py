#!/usr/bin/env python3
"""Tests for zyrinx_port — build-time Zyrinx (B&R "Moving Trucks") -> v0 song.

TDD: written before the implementation. Run via:
    python3 -m unittest tools.test_zyrinx_port
or
    python3 -m pytest tools/test_zyrinx_port.py -q

The transcoder turns the ALREADY-DECODED Moving Trucks JSON into our v0 music
format (a song_packer SongDesc). These tests pin the pure mapping functions
(note, tempo, duration) to reference values and check the flattening emits the
bounded-repeat opcode (no unrolling) wrapped in LoopPoint/Jump.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import zyrinx_port
from zyrinx_port import (
    zyrinx_note_to_pitch, zyrinx_tempo_to_byte, wait_to_dur,
    OCTAVE_BASE_OFFSET, DURATION_SCALE, ZYRINX_FORMAT_MOVING_TRUCKS,
    flatten_channel, build_songdesc, load_song,
)

import song_packer
from song_packer import (
    SongDesc, ChannelDesc, RepeatStart, RepeatEnd,
    Note, NoteDur, Rest, SetDur, Patch, Vol, LoopPoint, Jump,
    pack_song, MAX_PITCH,
    CHROUTE_FM1, CHROUTE_FM5,
)

# The decoded source JSON (the transcoder input).
_BR_DIR = ("/home/volence/sonic_hacks/The Adventures of Batman and Robin/"
           "disasm/sound/megadaw_export")
_JSON = os.path.join(_BR_DIR, "05_Moving_Trucks.json")


class TestNoteMapping(unittest.TestCase):
    """Our pitch index = Zyrinx note + transpose + OCTAVE_BASE_OFFSET, clamped."""

    def test_identity_with_zero_offset(self):
        # Pinned candidate: Zyrinx note value == our pitch index (offset 0).
        self.assertEqual(OCTAVE_BASE_OFFSET, 0)
        self.assertEqual(zyrinx_note_to_pitch(0), 0)
        self.assertEqual(zyrinx_note_to_pitch(57), 57)   # A4
        self.assertEqual(zyrinx_note_to_pitch(64), 64)

    def test_transpose_applied(self):
        self.assertEqual(zyrinx_note_to_pitch(64, transpose=-12), 52)
        self.assertEqual(zyrinx_note_to_pitch(40, transpose=+7), 47)

    def test_offset_applied(self):
        self.assertEqual(
            zyrinx_note_to_pitch(50, offset=3), 53)

    def test_clamp_high(self):
        # note 113 (= 101 + 12 transpose) exceeds MAX_PITCH(0x5E=94) -> clamp.
        self.assertEqual(zyrinx_note_to_pitch(120), MAX_PITCH)
        self.assertEqual(zyrinx_note_to_pitch(82, transpose=+40), MAX_PITCH)

    def test_clamp_low(self):
        self.assertEqual(zyrinx_note_to_pitch(5, transpose=-20), 0)

    def test_monotonic(self):
        prev = -1
        for n in range(0, 95):
            p = zyrinx_note_to_pitch(n)
            self.assertGreaterEqual(p, prev)
            prev = p


class TestTempoMapping(unittest.TestCase):
    """Zyrinx format code -> our Timer-A tempo byte. Timer-A overflow rate
    (N = tempo<<2, period = 18.773us*(1024-N)) bottoms out near ~52 Hz at
    tempo 0, so the original's ~17.14 events/sec is reproduced by tempo at the
    floor + the DURATION_SCALE factor (see TestDuration)."""

    def test_format_56_returns_byte(self):
        tb = zyrinx_tempo_to_byte(ZYRINX_FORMAT_MOVING_TRUCKS)
        self.assertTrue(0 <= tb <= 0xFF)

    def test_floor_tempo_for_slow_song(self):
        # Moving Trucks ($38=56, ~17.14 ev/s) is slower than Timer-A's floor,
        # so it pins to the slowest tempo byte (0 -> N=0 -> ~52 Hz).
        self.assertEqual(zyrinx_tempo_to_byte(ZYRINX_FORMAT_MOVING_TRUCKS), 0)

    def test_tempo_delta_does_not_overflow(self):
        # tempo_delta is added in Zyrinx event/sec terms; the byte stays valid.
        for delta in (-8, -2, 0, 2, 8):
            tb = zyrinx_tempo_to_byte(ZYRINX_FORMAT_MOVING_TRUCKS, delta)
            self.assertTrue(0 <= tb <= 0xFF, (delta, tb))


class TestDuration(unittest.TestCase):
    """wait `frames` -> our duration ticks. Our tick rate is ~DURATION_SCALE x
    the original event rate, so a frame maps to DURATION_SCALE ticks."""

    def test_scale_constant(self):
        # 52 Hz (Timer-A floor) / 17.14 (original) ~= 3.03 -> integer 3.
        self.assertEqual(DURATION_SCALE, 3)

    def test_frames_to_dur(self):
        self.assertEqual(wait_to_dur(1), DURATION_SCALE)
        self.assertEqual(wait_to_dur(31), 31 * DURATION_SCALE)

    def test_zero_frames(self):
        self.assertEqual(wait_to_dur(0), 0)

    def test_max_frame_fits_notedur(self):
        # Largest wait in the song is 63 frames; 63*3 = 189 <= 0xFF (NoteDur).
        self.assertLessEqual(wait_to_dur(63), 0xFF)


class TestFlatten(unittest.TestCase):
    """Each pattern emits its sequence body ONCE wrapped in RepeatStart/
    RepeatEnd(repeat) (NO unrolling); the channel is wrapped LoopPoint..Jump."""

    @staticmethod
    def _seqs():
        # Two tiny sequences. 4 = single held note (Moving-Trucks-shaped);
        # 9 = a 2-note body + loop terminator.
        return {
            "4": {"events": [
                {"type": "pitch", "pitches": [57], "tick": 0},
                {"type": "voice", "index": 40, "tick": 0},
                {"type": "wait", "frames": 31, "tick": 0},
                {"type": "loop", "tick": 31},
            ], "total_ticks": 31},
            "9": {"events": [
                {"type": "pitch", "pitches": [60], "tick": 0},
                {"type": "wait", "frames": 1, "tick": 0},
                {"type": "wait", "frames": 2, "tick": 1},   # rest (no pitch)
                {"type": "loop", "tick": 3},
            ], "total_ticks": 3},
        }

    def test_pattern_wrapped_in_repeat(self):
        ch = {"channel_idx": 0, "patterns": [
            {"seq_idx": 4, "repeat": 2, "pitch_transpose": 0, "tempo_delta": 0},
        ]}
        evs = flatten_channel(ch, self._seqs(), CHROUTE_FM1)
        types = [type(e).__name__ for e in evs]
        # LoopPoint ... RepeatStart, <body>, RepeatEnd ... Jump
        self.assertIn("RepeatStart", types)
        self.assertIn("RepeatEnd", types)
        rs = types.index("RepeatStart")
        re_ = types.index("RepeatEnd")
        self.assertLess(rs, re_)
        # The RepeatEnd carries the pattern's repeat count.
        self.assertEqual(evs[re_].count, 2)

    def test_note_then_wait_is_notedur(self):
        ch = {"channel_idx": 0, "patterns": [
            {"seq_idx": 4, "repeat": 1, "pitch_transpose": 0, "tempo_delta": 0},
        ]}
        evs = flatten_channel(ch, self._seqs(), CHROUTE_FM1)
        nd = [e for e in evs if isinstance(e, NoteDur)]
        self.assertEqual(len(nd), 1)
        self.assertEqual(nd[0].pitch, 57)
        self.assertEqual(nd[0].dur, wait_to_dur(31))

    def test_transpose_applied_in_body(self):
        ch = {"channel_idx": 0, "patterns": [
            {"seq_idx": 4, "repeat": 1, "pitch_transpose": -12, "tempo_delta": 0},
        ]}
        evs = flatten_channel(ch, self._seqs(), CHROUTE_FM1)
        nd = [e for e in evs if isinstance(e, NoteDur)]
        self.assertEqual(nd[0].pitch, 57 - 12)

    def test_wait_without_pitch_is_rest(self):
        ch = {"channel_idx": 0, "patterns": [
            {"seq_idx": 9, "repeat": 1, "pitch_transpose": 0, "tempo_delta": 0},
        ]}
        evs = flatten_channel(ch, self._seqs(), CHROUTE_FM1)
        self.assertTrue(any(isinstance(e, Rest) for e in evs))

    def test_voice_pan_volume_dropped_in_t1(self):
        # T1: voice -> Patch(0) placeholder is emitted in setup, not inline.
        # pan/volume events DROP. The body contains no Vol/Patch from the voice.
        ch = {"channel_idx": 0, "patterns": [
            {"seq_idx": 4, "repeat": 1, "pitch_transpose": 0, "tempo_delta": 0},
        ]}
        evs = flatten_channel(ch, self._seqs(), CHROUTE_FM1)
        # No inline Patch inside the repeat body (voice 40 was dropped).
        # The only Patch is the leading setup Patch(0) before LoopPoint.
        rs = next(i for i, e in enumerate(evs) if isinstance(e, RepeatStart))
        body = evs[rs:]
        self.assertFalse(any(isinstance(e, Patch) for e in body))

    def test_channel_loop_wrapping(self):
        ch = {"channel_idx": 0, "patterns": [
            {"seq_idx": 4, "repeat": 1, "pitch_transpose": 0, "tempo_delta": 0},
        ]}
        evs = flatten_channel(ch, self._seqs(), CHROUTE_FM1)
        # FM channel: leading Patch(0)+Vol(...) setup, then LoopPoint, ... Jump.
        self.assertIsInstance(evs[0], Patch)
        self.assertIsInstance(evs[1], Vol)
        self.assertTrue(any(isinstance(e, LoopPoint) for e in evs))
        self.assertIsInstance(evs[-1], Jump)


class TestBuildSongDesc(unittest.TestCase):
    """The full transcode packs through song_packer without error and stays
    compact (bounded-repeat, NOT unrolled)."""

    def setUp(self):
        if not os.path.exists(_JSON):
            self.skipTest("Moving Trucks JSON not present")
        self.raw = load_song(_JSON)
        self.song = build_songdesc(self.raw)

    def test_returns_songdesc(self):
        self.assertIsInstance(self.song, SongDesc)

    def test_packer_accepts(self):
        blob = pack_song(self.song)
        self.assertGreater(len(blob), 0)

    def test_six_fm_channels(self):
        # ch0-5 -> FM1..FM5 + the 6th held aside for T3 (FM6). The stub ch6 is
        # dropped. So T1 ships 5 routed FM channels (FM1..FM5).
        routes = [c.route for c in self.song.channels]
        self.assertEqual(routes, [CHROUTE_FM1, CHROUTE_FM1 + 1, CHROUTE_FM1 + 2,
                                  CHROUTE_FM1 + 3, CHROUTE_FM5])

    def test_compact_not_unrolled(self):
        # Bounded repeat keeps it a few KB; a full unroll would be ~100KB.
        blob = pack_song(self.song)
        self.assertLess(len(blob), 32 * 1024, "song looks unrolled (>32KB)")


if __name__ == "__main__":
    unittest.main()
