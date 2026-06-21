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

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import zyrinx_port
from zyrinx_port import (
    zyrinx_note_to_pitch, zyrinx_tempo_to_byte, wait_to_dur,
    OCTAVE_BASE_OFFSET, DURATION_SCALE, ZYRINX_FORMAT_MOVING_TRUCKS,
    flatten_channel, build_songdesc, load_song,
    translate_voice, OP_REORDER, build_patch_bank,
    FMPATCH_LEN,
)

# The global Zyrinx voice bank (Moving Trucks = bank1). The transcoder indexes
# this with the song's absolute VOICE indices.
_VOICES_JSON = ("/home/volence/sonic_hacks/The Adventures of Batman and Robin/"
                "disasm/sound/decoded_full/voices.json")

import song_packer
from song_packer import (
    SongDesc, ChannelDesc, RepeatStart, RepeatEnd,
    Note, NoteDur, Rest, SetDur, Patch, Vol, LoopPoint, Jump,
    pack_song, MAX_PITCH,
    CHROUTE_FM1, CHROUTE_FM5, CHROUTE_FM6,
    SH_F_FM6_FM, SH_F_STREAM,
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
        # Sound 1D T3: ch0-5 -> FM1..FM6 (all 6 active FM voices; ch5 -> FM6 via
        # the adaptive FM6 slot). The stub ch6 is dropped. So 6 routed FM channels.
        routes = [c.route for c in self.song.channels]
        self.assertEqual(routes, [CHROUTE_FM1, CHROUTE_FM1 + 1, CHROUTE_FM1 + 2,
                                  CHROUTE_FM1 + 3, CHROUTE_FM5, CHROUTE_FM6])

    def test_stream_fm6_flags(self):
        # The song declares FM6=FM voice + stream-from-ROM, so the loader takes the
        # DAC-off stream path.
        self.assertEqual(self.song.flags, SH_F_FM6_FM | SH_F_STREAM)

    def test_compact_not_unrolled(self):
        # Bounded repeat keeps it a few KB; a full unroll would be ~100KB.
        blob = pack_song(self.song)
        self.assertLess(len(blob), 32 * 1024, "song looks unrolled (>32KB)")


class TestTranslateVoice(unittest.TestCase):
    """Zyrinx voices.json entry -> 26-byte FmPatch (our format). The op reorder
    maps Zyrinx natural [op1,op2,op3,op4] -> our physical [S1,S3,S2,S4] =
    natural indices [0,2,1,3] (calibrated against the VGM in T5)."""

    def test_op_reorder_constant(self):
        # The Bank2 ROM voices are ALREADY stored in YM physical-register order
        # (the driver writes them straight to $30/$34/$38/$3C), so translate_voice
        # must NOT reorder. Verified against the live B&R FM2 register capture: a
        # [0,2,1,3] reorder swapped operators S2<->S3 and made every voice's timbre
        # wrong. (The old reorder was calibrated against the WRONG song, song_05.)
        self.assertEqual(OP_REORDER, [0, 1, 2, 3])
        g = [10, 20, 30, 40]
        self.assertEqual([g[i] for i in OP_REORDER], [10, 20, 30, 40])

    def test_bank1_voice0_byte_exact(self):
        # voices.json bank1[0]: fb=1, algo=3, ams_fms_pan=240 ($F0, L/R set).
        v = {
            "fb": 1, "algo": 3,
            "dt_mul": [119, 123, 72, 127],
            "tl":     [103,   0, 112, 105],
            "ks_ar":  [ 11,   0,  11,  12],
            "am_d1r": [ 16,  16,  16,  16],
            "d2r":    [  0,   0,   0,   0],
            "sl_rr":  [  7,  10,   7,  58],
            "ams_fms_pan": 240,
            "ext": [0, 60, 36, 0],
        }
        # Hand-computed expected (NO reorder -- ROM voices are already in physical
        # order, so each op group passes straight through; verified vs the live
        # B&R FM2 register capture):
        #   fp_alg_fb     = (1<<3)|3 = 11
        #   fp_lr_ams_fms = 240 (L/R bits 6-7 already set -> kept as-is)
        #   dt_mul  [119,123,72,127] -> [119,123, 72,127]
        #   tl      [103,  0,112,105] -> INVERTED (0x7F^x): [ 24,127, 15, 22]
        #   ks_ar   [ 11,  0, 11, 12] -> [ 11,  0, 11, 12]
        #   am_d1r  [ 16, 16, 16, 16] -> [ 16, 16, 16, 16]
        #   d2r     [  0,  0,  0,  0] -> [  0,  0,  0,  0]
        #   sl_rr   [  7, 10,  7, 58] -> [  7, 10,  7, 58]
        # NOTE: translate_voice inverts TL (0x7F XOR) — Zyrinx stores TL as LEVEL
        # (high=loud); the YM2612 reg is ATTENUATION (high=quiet). This inversion
        # is the correct, song-agnostic fix; the $40 row below is the inverted form.
        expected = bytes([
            11,                     # fp_alg_fb
            240,                    # fp_lr_ams_fms
            119, 123, 72, 127,      # fp_dt_mul   ($30) straight-through
            24, 127, 15, 22,        # fp_tl       ($40)  = 0x7F ^ [103,0,112,105]
            11, 0, 11, 12,          # fp_rs_ar    ($50) <- ks_ar
            16, 16, 16, 16,         # fp_am_d1r   ($60)
            0, 0, 0, 0,             # fp_d2r      ($70)
            7, 10, 7, 58,           # fp_d1l_rr   ($80) <- sl_rr
        ])
        out = translate_voice(v)
        self.assertEqual(len(out), 26)
        self.assertEqual(len(out), FMPATCH_LEN)
        self.assertEqual(out, expected)

    def test_alg_fb_composition(self):
        # fp_alg_fb = ((fb&7)<<3) | (algo&7). Masks both fields.
        v = self._neutral()
        v["fb"], v["algo"] = 7, 5
        self.assertEqual(translate_voice(v)[0], (7 << 3) | 5)
        v["fb"], v["algo"] = 0, 0
        self.assertEqual(translate_voice(v)[0], 0)
        # Fields are masked to 3 bits each (overflow bits dropped).
        v["fb"], v["algo"] = 0xFF, 0xFF
        self.assertEqual(translate_voice(v)[0], (7 << 3) | 7)

    def test_lr_bits_forced_when_clear(self):
        # voices.json bank1[108] is all-zero with ams_fms_pan=0 (L/R clear):
        # force L/R=11 ($C0) so the channel is audible.
        v = self._neutral()
        v["ams_fms_pan"] = 0
        self.assertEqual(translate_voice(v)[1], 0xC0)
        # Only one L/R bit set is still "not 11" -> forced full.
        v["ams_fms_pan"] = 0x40       # L only
        self.assertEqual(translate_voice(v)[1], 0x40 | 0xC0)
        v["ams_fms_pan"] = 0x80       # R only
        self.assertEqual(translate_voice(v)[1], 0x80 | 0xC0)

    def test_lr_bits_kept_when_both_set(self):
        v = self._neutral()
        v["ams_fms_pan"] = 0xC6       # L/R=11 + FMS bits -> kept verbatim
        self.assertEqual(translate_voice(v)[1], 0xC6)

    def test_reorder_applied_per_group(self):
        v = self._neutral()
        v["dt_mul"] = [1, 2, 3, 4]
        out = translate_voice(v)
        # No reorder: ROM voices are already in physical order -> straight through.
        self.assertEqual(list(out[2:6]), [1, 2, 3, 4])

    def test_tl_inversion_is_skippable_for_sfx(self):
        # YM2612 TL is ATTENUATION. Zyrinx voices store TL as LEVEL, so the default
        # inverts (0x7F ^). S3K smpsVcTotalLevel voices are ALREADY attenuation, so
        # tl_is_level=False stores them verbatim. Regression guard for the FM-SFX
        # "wrong sound" bug: inverting S3K TL silenced the loud carriers.
        v = self._neutral()
        v["tl"] = [0x00, 0x1C, 0x00, 0x00]                  # S3K spindash: loud carriers
        self.assertEqual(list(translate_voice(v)[6:10]),
                         [0x7F, 0x63, 0x7F, 0x7F],
                         "default (Zyrinx LEVEL) path inverts TL")
        self.assertEqual(list(translate_voice(v, tl_is_level=False)[6:10]),
                         [0x00, 0x1C, 0x00, 0x00],
                         "tl_is_level=False keeps S3K attenuation TL verbatim (loud carriers)")

    def test_ext_dropped(self):
        # ext[4] is not present in the 26-byte output (length proves it).
        self.assertEqual(len(translate_voice(self._neutral())), 26)

    @staticmethod
    def _neutral():
        return {
            "fb": 0, "algo": 0,
            "dt_mul": [0, 0, 0, 0], "tl": [0, 0, 0, 0],
            "ks_ar": [0, 0, 0, 0], "am_d1r": [0, 0, 0, 0],
            "d2r": [0, 0, 0, 0], "sl_rr": [0, 0, 0, 0],
            "ams_fms_pan": 0xC0, "ext": [0, 0, 0, 0],
        }


class TestPatchBank(unittest.TestCase):
    """The per-song dense patch bank + voice_idx -> local_idx remap. The bank is
    built from the distinct voice indices the song references, in first-seen
    order, each translated to a 26-byte FmPatch."""

    def setUp(self):
        if not os.path.exists(_JSON) or not os.path.exists(_VOICES_JSON):
            self.skipTest("Moving Trucks / voices JSON not present")
        self.raw = load_song(_JSON)
        self.bank_bytes, self.remap, self.count = build_patch_bank(
            self.raw, _VOICES_JSON)

    def test_bank_is_n_records_of_26(self):
        self.assertGreater(self.count, 0)
        self.assertEqual(len(self.bank_bytes), self.count * 26)
        self.assertEqual(len(self.remap), self.count)

    def test_remap_is_dense_0_to_n(self):
        # Local indices form a dense 0..N-1 set (no gaps, no dups).
        self.assertEqual(sorted(self.remap.values()), list(range(self.count)))

    def test_remap_first_seen_order(self):
        # First-seen voice index maps to local 0, etc. (deterministic order).
        first_voice = None
        for ch in self.raw["channels"]:
            for pat in ch.get("patterns", []):
                seq = self.raw["sequences"].get(str(pat["seq_idx"]))
                if not seq:
                    continue
                for ev in seq["events"]:
                    if ev["type"] == "voice":
                        first_voice = ev["index"]
                        break
                if first_voice is not None:
                    break
            if first_voice is not None:
                break
        self.assertIsNotNone(first_voice)
        self.assertEqual(self.remap[first_voice], 0)

    def test_each_record_matches_translate_voice(self):
        with open(_VOICES_JSON) as f:
            v = json.load(f)["bank1"]
        for voice_idx, local_idx in self.remap.items():
            off = local_idx * 26
            rec = self.bank_bytes[off:off + 26]
            self.assertEqual(rec, translate_voice(v[voice_idx]),
                             f"voice {voice_idx} -> local {local_idx}")

    def test_song_uses_local_patch_indices(self):
        # build_songdesc must emit Patch(local_idx) for the voices, and the local
        # indices must all be < the bank count.
        song = build_songdesc(self.raw, voices_json=_VOICES_JSON)
        patch_vals = [e.patch for c in song.channels for e in c.events
                      if isinstance(e, Patch)]
        self.assertTrue(patch_vals, "no Patch events emitted")
        for p in patch_vals:
            self.assertTrue(0 <= p < self.count, f"local patch {p} out of bank")


if __name__ == "__main__":
    unittest.main()
