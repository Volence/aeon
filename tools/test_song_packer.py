#!/usr/bin/env python3
"""Tests for song_packer — build-time music song -> bytes + .asm.

TDD: written before the implementation. Run via:
    python3 -m pytest tools/test_song_packer.py -q
"""

import unittest
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import song_packer
from song_packer import (
    SongDesc, ChannelDesc,
    SetDur, Rest, Note, Vol, Patch, Dac, NoteDur, LoopPoint, Jump, End,
    RepeatStart, RepeatEnd, Pan, OpBias, RegDelta, reg_sel, Detune,
    pack_song, emit_asm, PackError,
    MEV_REPEAT_START, MEV_REPEAT_END, MEV_PAN, MEV_OPBIAS, MEV_REGDELTA, MEV_DETUNE,
    RD_GROUP_TL, RD_GROUP_DT_MUL, RD_GROUP_D1L_RR, REGDELTA_GROUP_COUNT,
)

# Route constants mirrored from sound_constants.asm (kept in sync by hand;
# the packer also exposes them).
from song_packer import (
    CHROUTE_FM1, CHROUTE_FM6, CHROUTE_PSG1, CHROUTE_PSGN, CHROUTE_DAC,
    SH_F_FM6_FM, SH_F_STREAM,
)


class TestEventEncoding(unittest.TestCase):

    def test_set_dur(self):
        self.assertEqual(SetDur(0x20).encode(), bytes([0x20]))

    def test_rest(self):
        self.assertEqual(Rest().encode(), bytes([0x80]))

    def test_note(self):
        self.assertEqual(Note(0).encode(), bytes([0x81]))
        self.assertEqual(Note(0x5E).encode(), bytes([0x81 + 0x5E]))

    def test_vol(self):
        self.assertEqual(Vol(64).encode(), bytes([0xE0, 0x40]))

    def test_patch(self):
        self.assertEqual(Patch(3).encode(), bytes([0xE1, 0x03]))

    def test_dac(self):
        self.assertEqual(Dac(7).encode(), bytes([0xE2, 0x07]))

    def test_note_dur(self):
        self.assertEqual(NoteDur(3, 8).encode(), bytes([0xE3, 0x03, 0x08]))

    def test_repeat_start(self):
        self.assertEqual(RepeatStart().encode(), bytes([MEV_REPEAT_START]))
        self.assertEqual(MEV_REPEAT_START, 0xE5)

    def test_repeat_end(self):
        self.assertEqual(RepeatEnd(4).encode(), bytes([MEV_REPEAT_END, 0x04]))
        self.assertEqual(MEV_REPEAT_END, 0xE6)
        self.assertEqual(RepeatEnd(255).encode(), bytes([MEV_REPEAT_END, 0xFF]))

    def test_pan(self):
        self.assertEqual(Pan(0x80).encode(), bytes([MEV_PAN, 0x80]))
        self.assertEqual(MEV_PAN, 0xE4)
        # hardware-correct $B4 L/R bits: bit7 = Left, bit6 = Right, $C0 = both.
        self.assertEqual(Pan.PAN_LEFT, 0x80)
        self.assertEqual(Pan.PAN_RIGHT, 0x40)
        self.assertEqual(Pan.PAN_CENTER, 0xC0)

    def test_opbias(self):
        self.assertEqual(OpBias(2, 0x30).encode(), bytes([MEV_OPBIAS, 0x02, 0x30]))
        self.assertEqual(MEV_OPBIAS, 0xE9)

    def test_opbias_signed_encode(self):
        # val is signed -128..127, encoded as a two's-complement byte.
        self.assertEqual(OpBias(0, -16).encode(), bytes([MEV_OPBIAS, 0x00, 0xF0]))
        self.assertEqual(OpBias(1, -1).encode(),  bytes([MEV_OPBIAS, 0x01, 0xFF]))
        self.assertEqual(OpBias(2, -128).encode(), bytes([MEV_OPBIAS, 0x02, 0x80]))
        self.assertEqual(OpBias(3, 127).encode(),  bytes([MEV_OPBIAS, 0x03, 0x7F]))

    def test_opbias_signed_range_valid(self):
        # boundary values -128 and 127 must validate cleanly on an FM route.
        OpBias(0, -128).validate(CHROUTE_FM1)
        OpBias(0, 127).validate(CHROUTE_FM1)

    def test_opbias_val_out_of_range(self):
        with self.assertRaises(PackError):
            OpBias(0, 128).validate(CHROUTE_FM1)
        with self.assertRaises(PackError):
            OpBias(0, -129).validate(CHROUTE_FM1)

    def test_detune_encode(self):
        self.assertEqual(Detune(0x10).encode(), bytes([MEV_DETUNE, 0x10]))
        self.assertEqual(Detune(-1).encode(), bytes([MEV_DETUNE, 0xFF]))
        self.assertEqual(Detune(-128).encode(), bytes([MEV_DETUNE, 0x80]))

    def test_detune_range(self):
        Detune(-128).validate(CHROUTE_FM1)   # signed-byte boundaries OK (FM + PSG)
        Detune(127).validate(CHROUTE_PSG1)
        with self.assertRaises(PackError):
            Detune(200).validate(CHROUTE_FM1)
        with self.assertRaises(PackError):
            Detune(-200).validate(CHROUTE_FM1)

    def test_reg_sel_encoding(self):
        # reg_sel = (group_code << 2) | op. TL group op0 = the canonical lead step.
        self.assertEqual(reg_sel(RD_GROUP_TL, 0), 0x04)   # ($40 group) -> (1<<2)|0
        self.assertEqual(reg_sel(RD_GROUP_DT_MUL, 0), 0x00)  # ($30 group) op0
        self.assertEqual(reg_sel(RD_GROUP_TL, 3), 0x07)   # TL group, op3 (carrier S4)
        self.assertEqual(reg_sel(RD_GROUP_D1L_RR, 2), (5 << 2) | 2)  # $80 group, op2
        with self.assertRaises(PackError):
            reg_sel(RD_GROUP_TL, 4)                        # op out of 0..3
        with self.assertRaises(PackError):
            reg_sel(REGDELTA_GROUP_COUNT, 0)               # group_code out of range

    def test_regdelta_encode(self):
        self.assertEqual(MEV_REGDELTA, 0xEA)
        # single (reg_sel, value): count=1, the lead TL voice-step.
        self.assertEqual(RegDelta.tl(0, 0x38).encode(),
                         bytes([MEV_REGDELTA, 0x01, 0x04, 0x38]))
        # explicit multi-entry: count + count*(reg_sel, value) pairs.
        self.assertEqual(
            RegDelta([(0x04, 0x20), (reg_sel(RD_GROUP_DT_MUL, 1), 0x02)]).encode(),
            bytes([MEV_REGDELTA, 0x02, 0x04, 0x20, 0x01, 0x02]))

    def test_regdelta_on_non_fm_route(self):
        with self.assertRaises(PackError):
            RegDelta.tl(0, 0x38).validate(CHROUTE_PSG1)

    def test_regdelta_bad_group_code(self):
        # a reg_sel whose group_code field exceeds the table must be rejected.
        bad = (REGDELTA_GROUP_COUNT << 2) | 0
        with self.assertRaises(PackError):
            RegDelta([(bad, 0x00)]).validate(CHROUTE_FM1)

    def test_regdelta_zero_tick_in_loop_body_still_needs_a_note(self):
        # RegDelta is zero-tick: a loop body of ONLY RegDeltas would spin forever,
        # so the packer must still require a time-advancing event (PitchEnv here).
        from song_packer import PitchEnv
        ok = SongDesc(tempo=16, channels=[ChannelDesc(CHROUTE_FM1, [
            Patch(1), Vol(110), SetDur(1), LoopPoint(),
            PitchEnv(0x30), RegDelta.tl(0, 0x20), PitchEnv(0x30), Jump(),
        ])])
        pack_song(ok)   # must not raise
        spin = SongDesc(tempo=16, channels=[ChannelDesc(CHROUTE_FM1, [
            Patch(1), Vol(110), SetDur(1), LoopPoint(),
            RegDelta.tl(0, 0x20), Jump(),
        ])])
        with self.assertRaises(PackError):
            pack_song(spin)

    def test_loop_point(self):
        self.assertEqual(LoopPoint().encode(), bytes([0xEE]))

    def test_jump(self):
        self.assertEqual(Jump().encode(), bytes([0xEF]))

    def test_end(self):
        self.assertEqual(End().encode(), bytes([0xFF]))


def _simple_song():
    # 2 channels, both well-formed and looping. Each sends its required setup
    # (FM: Patch+Vol; PSG: Vol) before its first time-advancing event.
    return SongDesc(tempo=6, channels=[
        ChannelDesc(CHROUTE_FM1, [
            Patch(0), Vol(100), SetDur(0x10), LoopPoint(), Note(57), Rest(), Jump(),
        ]),
        ChannelDesc(CHROUTE_PSG1, [
            Vol(90), SetDur(0x10), LoopPoint(), Note(57), Jump(),
        ]),
    ])


class TestHeader(unittest.TestCase):

    def setUp(self):
        self.song = _simple_song()
        self.blob = pack_song(self.song)

    def test_flags_tempo_and_count(self):
        # Phase 3 header: flags(+0), tempo(+1), tempo_base(+2), channel_count(+3).
        self.assertEqual(self.blob[0], 0)        # default flags = 0 (1C copy/DAC)
        self.assertEqual(self.blob[1], 6)        # tempo (legacy Timer-A selector)
        # tempo_base default clamps the legacy tempo (6) up to the 16 floor so
        # the per-frame accumulator never mis-plays (one event-tick/frame cap).
        self.assertEqual(self.blob[2], 16)
        self.assertEqual(self.blob[3], 2)        # channel count
        # pitchtable_ptr (+4, dw) = 0 (engine default).
        self.assertEqual((self.blob[4] << 8) | self.blob[5], 0)

    def test_channel_routes_and_pointers(self):
        # Header: flags, tempo, tempo_base, count, dw pitchtable_ptr, then per
        # channel (route, dw cmd_ptr, dw mod_ptr), then dw patch_table_ptr.
        # Pointers are big-endian offsets within the blob.
        off = 6                                  # skip flags,tempo,tempo_base,count,pitchtab(2)
        ptrs = []
        for ch in self.song.channels:
            self.assertEqual(self.blob[off], ch.route)
            ptr = (self.blob[off + 1] << 8) | self.blob[off + 2]
            ptrs.append(ptr)
            # mod_ptr (slot[1]) is 0/NULL for single-stream A.
            self.assertEqual((self.blob[off + 3] << 8) | self.blob[off + 4], 0)
            off += 5
        # patch_table_ptr word follows
        off += 2
        # The first stream pointer should point at the first byte after the
        # full header; subsequent ones follow each stream's length.
        header_len = 4 + 2 + 5 * len(self.song.channels) + 2
        self.assertEqual(ptrs[0], header_len)
        # Stream 0 bytes equal the encoded events; pointer 1 = ptr0 + len(stream0)
        s0 = b"".join(e.encode() for e in self.song.channels[0].events)
        self.assertEqual(ptrs[1], ptrs[0] + len(s0))
        # The bytes at ptr0 match stream 0.
        self.assertEqual(self.blob[ptrs[0]:ptrs[0] + len(s0)], s0)

    def test_flags_emitted(self):
        # A song with explicit flags emits them as header byte 0.
        song = SongDesc(tempo=6, flags=SH_F_FM6_FM | SH_F_STREAM, channels=[
            ChannelDesc(CHROUTE_FM1, [
                Patch(0), Vol(100), SetDur(0x10), LoopPoint(), Note(57), Jump()])])
        self.assertEqual(pack_song(song)[0], SH_F_FM6_FM | SH_F_STREAM)

    def test_tempo_base_emitted(self):
        # tempo_base packs at +2 (distinct from the legacy tempo at +1).
        song = SongDesc(tempo=6, tempo_base=0x38, channels=[
            ChannelDesc(CHROUTE_FM1, [
                Patch(0), Vol(100), SetDur(0x10), LoopPoint(), Note(57), Jump()])])
        blob = pack_song(song)
        self.assertEqual(blob[1], 6)
        self.assertEqual(blob[2], 0x38)

    def test_streams_present(self):
        # Concatenated streams appear after the header in order.
        header_len = 4 + 2 + 5 * 2 + 2
        body = self.blob[header_len:]
        expect = b""
        for ch in self.song.channels:
            expect += b"".join(e.encode() for e in ch.events)
        self.assertEqual(body, expect)


class TestValidation(unittest.TestCase):

    def _pack(self, channels, tempo=6):
        return pack_song(SongDesc(tempo=tempo, channels=channels))

    def test_note_pitch_too_high(self):
        with self.assertRaises(PackError):
            self._pack([ChannelDesc(CHROUTE_FM1,
                        [LoopPoint(), Note(0x5F), Jump()])])

    def test_set_dur_too_high(self):
        with self.assertRaises(PackError):
            self._pack([ChannelDesc(CHROUTE_FM1,
                        [SetDur(0x80), LoopPoint(), Note(0), Jump()])])

    def test_dac_on_non_dac_route(self):
        with self.assertRaises(PackError):
            self._pack([ChannelDesc(CHROUTE_FM1,
                        [LoopPoint(), Dac(1), Jump()])])

    def test_patch_on_non_fm_route(self):
        with self.assertRaises(PackError):
            self._pack([ChannelDesc(CHROUTE_PSG1,
                        [Patch(0), LoopPoint(), Note(0), Jump()])])

    def test_opbias_on_non_fm_route(self):
        with self.assertRaises(PackError):
            self._pack([ChannelDesc(CHROUTE_PSG1,
                        [Vol(64), LoopPoint(), OpBias(0, 0x10), Note(0), Jump()])])

    def test_opbias_op_out_of_range(self):
        with self.assertRaises(PackError):
            OpBias(4, 0x10).validate(CHROUTE_FM1)

    def test_pan_then_opbias_then_patch_packs(self):
        # A well-formed FM channel using Pan + OpBias (FM-only coordination setters).
        blob = self._pack([ChannelDesc(CHROUTE_FM1, [
            Patch(1), Vol(110), SetDur(59), LoopPoint(),
            Pan(Pan.PAN_LEFT), OpBias(0, 0x30), Patch(1), Note(0), Jump(),
        ])])
        # the stream contains the $E4/$E9 opcodes in order.
        self.assertIn(bytes([MEV_PAN, 0x80]), blob)
        self.assertIn(bytes([MEV_OPBIAS, 0x00, 0x30]), blob)

    def test_jump_without_loop_point(self):
        # Setup is in place so this isolates the Jump-without-LoopPoint check.
        with self.assertRaises(PackError):
            self._pack([ChannelDesc(CHROUTE_FM1,
                        [Patch(0), Vol(64), Note(0), Jump()])])

    def test_unterminated_stream(self):
        # Setup is in place so this isolates the unterminated-stream check.
        with self.assertRaises(PackError):
            self._pack([ChannelDesc(CHROUTE_FM1,
                        [Patch(0), Vol(64), Note(0), Rest()])])

    def test_end_terminator_ok(self):
        # End() is a valid terminator (one-shot, no loop).
        blob = self._pack([ChannelDesc(CHROUTE_FM1,
                          [Patch(0), Vol(64), Note(0), End()])])
        self.assertEqual(blob[-2:], bytes([0x81, 0xFF]))

    def test_dac_route_allows_dac(self):
        blob = self._pack([ChannelDesc(CHROUTE_DAC,
                          [LoopPoint(), Dac(1), Rest(), Jump()])])
        self.assertIn(0xE2, blob)

    def test_empty_loop_body_rejected(self):
        # LoopPoint immediately followed by Jump: the loop body advances no
        # time, so the Z80 fetch loop would spin forever. Reject at pack time.
        with self.assertRaises(PackError):
            self._pack([ChannelDesc(CHROUTE_FM1, [LoopPoint(), Jump()])])

    def test_zero_tick_only_loop_body_rejected(self):
        # A loop body of only zero-tick events (Vol) still never advances time.
        with self.assertRaises(PackError):
            self._pack([ChannelDesc(CHROUTE_FM1,
                        [LoopPoint(), Vol(10), Jump()])])

    def test_loop_body_with_note_ok(self):
        # A loop body containing a time-advancing event (Note) is accepted.
        blob = self._pack([ChannelDesc(CHROUTE_FM1,
                          [Patch(0), Vol(64), LoopPoint(), Note(0), Jump()])])
        self.assertIn(0xEF, blob)

    # --- bounded-repeat opcodes (Sound 1D Task 1) ---

    def test_repeat_body_packs(self):
        # RepeatStart, <body>, RepeatEnd(n) round-trips inside a loop.
        blob = self._pack([ChannelDesc(CHROUTE_FM1, [
            Patch(0), Vol(64), LoopPoint(),
            RepeatStart(), Note(0), RepeatEnd(2), Jump()])])
        # ...E5 81 E6 02... appears in the stream.
        self.assertIn(bytes([MEV_REPEAT_START, 0x81, MEV_REPEAT_END, 0x02]),
                      blob)

    def test_repeat_end_without_start_rejected(self):
        with self.assertRaises(PackError):
            self._pack([ChannelDesc(CHROUTE_FM1, [
                Patch(0), Vol(64), LoopPoint(), Note(0), RepeatEnd(2), Jump()])])

    def test_repeat_start_unclosed_rejected(self):
        with self.assertRaises(PackError):
            self._pack([ChannelDesc(CHROUTE_FM1, [
                Patch(0), Vol(64), LoopPoint(), RepeatStart(), Note(0), Jump()])])

    def test_repeat_count_zero_rejected(self):
        with self.assertRaises(PackError):
            self._pack([ChannelDesc(CHROUTE_FM1, [
                Patch(0), Vol(64), LoopPoint(),
                RepeatStart(), Note(0), RepeatEnd(0), Jump()])])

    def test_repeat_count_too_high_rejected(self):
        with self.assertRaises(PackError):
            self._pack([ChannelDesc(CHROUTE_FM1, [
                Patch(0), Vol(64), LoopPoint(),
                RepeatStart(), Note(0), RepeatEnd(256), Jump()])])


class TestSetupBeforeFirstNote(unittest.TestCase):
    """A channel's first time-advancing event (Note/Rest/NoteDur) keys a note on
    the YM2612 / SN76489. If it fires before the channel has been initialized,
    the chip plays an undefined voice/attenuation (power-on garbage register
    state). Enforce the setup at pack time (compile-time-validation mandate).

    Per route class:
      - FM routes (FM1..FM5): BOTH Patch ($E1) AND Vol ($E0) must appear before
        the first Note/Rest/NoteDur.
      - PSG routes (PSG1..PSGN): Vol ($E0) must appear before the first note
        (PSG has no patch concept — $E1 is already rejected on non-FM routes).
      - DAC route: exempt (only emits $E2 triggers; no patch/vol/notes).
    Setup-run events (Patch, Vol, SetDur, LoopPoint) may appear in any order
    before the first time-advancing event.
    """

    def _pack(self, channels, tempo=6):
        return pack_song(SongDesc(tempo=tempo, channels=channels))

    # --- FM: must have BOTH Patch and Vol before first note ---

    def test_fm_note_before_any_patch_rejected(self):
        with self.assertRaises(PackError):
            self._pack([ChannelDesc(CHROUTE_FM1,
                        [LoopPoint(), Note(0), Jump()])])

    def test_fm_patch_but_no_vol_before_note_rejected(self):
        with self.assertRaises(PackError):
            self._pack([ChannelDesc(CHROUTE_FM1,
                        [Patch(0), LoopPoint(), Note(0), Jump()])])

    def test_fm_vol_but_no_patch_before_note_rejected(self):
        with self.assertRaises(PackError):
            self._pack([ChannelDesc(CHROUTE_FM1,
                        [Vol(64), LoopPoint(), Note(0), Jump()])])

    def test_fm_patch_then_vol_then_note_accepted(self):
        blob = self._pack([ChannelDesc(CHROUTE_FM1,
                          [Patch(0), Vol(64), LoopPoint(), Note(0), Jump()])])
        self.assertIn(0xEF, blob)

    def test_fm_vol_then_patch_then_note_accepted(self):
        # Setup order is free — Vol before Patch is fine.
        blob = self._pack([ChannelDesc(CHROUTE_FM1,
                          [Vol(64), Patch(0), LoopPoint(), Note(0), Jump()])])
        self.assertIn(0xEF, blob)

    def test_fm_rest_is_time_advancing_for_setup_check(self):
        # The "first time-advancing event" includes Rest — keying happens via the
        # tick driver regardless of whether it's a Note or a Rest.
        with self.assertRaises(PackError):
            self._pack([ChannelDesc(CHROUTE_FM1,
                        [Patch(0), LoopPoint(), Rest(), Note(0), Jump()])])

    def test_fm_notedur_is_time_advancing_for_setup_check(self):
        with self.assertRaises(PackError):
            self._pack([ChannelDesc(CHROUTE_FM1,
                        [Vol(64), LoopPoint(), NoteDur(0, 8), Jump()])])

    # --- PSG: must have Vol before first note (no patch concept) ---

    def test_psg_note_before_any_vol_rejected(self):
        with self.assertRaises(PackError):
            self._pack([ChannelDesc(CHROUTE_PSG1,
                        [LoopPoint(), Note(0), Jump()])])

    def test_psg_vol_then_note_accepted(self):
        blob = self._pack([ChannelDesc(CHROUTE_PSG1,
                          [Vol(64), LoopPoint(), Note(0), Jump()])])
        self.assertIn(0xEF, blob)

    def test_psgn_note_before_any_vol_rejected(self):
        with self.assertRaises(PackError):
            self._pack([ChannelDesc(CHROUTE_PSGN,
                        [LoopPoint(), Note(0), Jump()])])

    # --- DAC: exempt ---

    def test_dac_triggers_only_accepted(self):
        # DAC channel emits only Dac triggers (+ Rest/loop) and no patch/vol —
        # it is exempt from the setup-before-first-note rule.
        blob = self._pack([ChannelDesc(CHROUTE_DAC,
                          [SetDur(0x20), LoopPoint(), Dac(1), Rest(), Jump()])])
        self.assertIn(0xE2, blob)


class TestEmitAsm(unittest.TestCase):

    def setUp(self):
        self.song = _simple_song()
        self.asm = emit_asm(self.song, "Song_Test")

    def test_labeled(self):
        self.assertIn("Song_Test:", self.asm)

    def test_even_terminated(self):
        # AS in this build uses `align 2` (no `even` instruction).
        self.assertTrue(any(l.strip() == "align 2" for l in self.asm.splitlines()))

    def test_roundtrip_bytes(self):
        # Parse the dc.b values out of the .asm and compare to pack_song.
        vals = []
        for l in self.asm.splitlines():
            s = l.strip()
            m = re.match(r"dc\.b\s+(.*)", s)
            if m:
                for tok in m.group(1).split(","):
                    tok = tok.strip()
                    if not tok:
                        continue
                    if tok.startswith("$"):
                        vals.append(int(tok[1:], 16))
                    else:
                        vals.append(int(tok, 0))
        self.assertEqual(bytes(vals), pack_song(self.song))


class TestMacroEvents(unittest.TestCase):

    def test_new_mev_consts(self):
        self.assertEqual(song_packer.MEV_FMENV, 0xF7)
        self.assertEqual(song_packer.MEV_REGWRITE, 0xF8)
        self.assertEqual(song_packer.MEV_MACRO, 0xF9)

    def test_fmenv_encode(self):
        from song_packer import FmEnv
        self.assertEqual(FmEnv(3).encode(), bytes([0xF7, 0x03]))

    def test_fmenv_on_psg_route_rejected(self):
        from song_packer import FmEnv
        with self.assertRaises(PackError):
            FmEnv(3).validate(CHROUTE_PSG1)

    def test_fmenv_id_out_of_range(self):
        from song_packer import FmEnv
        with self.assertRaises(PackError):
            FmEnv(256).validate(CHROUTE_FM1)

    def test_regwrite_encode(self):
        from song_packer import RegWrite
        self.assertEqual(RegWrite(0, 0x90, 0x08).encode(),
                         bytes([0xF8, 0x00, 0x90, 0x08]))

    def test_regwrite_part_range(self):
        from song_packer import RegWrite
        with self.assertRaises(PackError):
            RegWrite(2, 0x90, 0x00).validate(CHROUTE_FM1)

    def test_regwrite_rejects_dac_regs(self):
        # $2A (DAC data) and $2B (DAC enable) corrupt/silence the DAC stream.
        from song_packer import RegWrite
        with self.assertRaises(PackError):
            RegWrite(0, 0x2A, 0x00).validate(CHROUTE_FM1)
        with self.assertRaises(PackError):
            RegWrite(0, 0x2B, 0x80).validate(CHROUTE_FM1)

    def test_regwrite_on_non_fm_route_rejected(self):
        from song_packer import RegWrite
        with self.assertRaises(PackError):
            RegWrite(0, 0x90, 0x00).validate(CHROUTE_PSG1)

    def test_macro_encode_default_ptr(self):
        # Macro encodes a 2-byte BE blob-offset operand; the offset is
        # back-patched by pack_song. The bare event encodes a placeholder 0.
        from song_packer import Macro
        self.assertEqual(Macro().encode(), bytes([0xF9, 0x00, 0x00]))

    def test_macro_on_psg_route_rejected(self):
        from song_packer import Macro
        with self.assertRaises(PackError):
            Macro().validate(CHROUTE_PSG1)

    def test_macro_encode_patched_ptr(self):
        # the 2-byte BE split must hold for a non-zero (back-patched) offset
        from song_packer import Macro
        m = Macro()
        m.body_offset = 0x0145
        self.assertEqual(m.encode(), bytes([0xF9, 0x01, 0x45]))

    # --- E2: slot[1] macro-body emitter + back-patched header mod_ptr ---

    def test_tag_consts(self):
        self.assertEqual(song_packer.TAG_MAC_NEXT, 0xE0)
        self.assertEqual(song_packer.TAG_MAC_REG, 0xE1)
        self.assertEqual(song_packer.TAG_MAC_LOOP, 0xE2)
        self.assertEqual(song_packer.TAG_MAC_END, 0xE3)

    def test_emit_macro_body_basic(self):
        # A reg write, a frame yield, then end.
        from song_packer import emit_macro_body, MacReg, MacNext, MacEnd
        body = emit_macro_body([MacReg(0, 0x90, 0x08), MacNext(), MacEnd()],
                               body_base=0)
        self.assertEqual(body, bytes([0xE1, 0x00, 0x90, 0x08, 0xE0, 0xE3]))

    def test_emit_macro_body_loop_target_is_be_body_base(self):
        # TAG_MAC_LOOP carries a 2-byte BE offset = the body's start in the blob.
        from song_packer import emit_macro_body, MacReg, MacNext, MacLoop
        body = emit_macro_body([MacReg(0, 0x90, 0x08), MacNext(), MacLoop()],
                               body_base=0x0140)
        # ...E0 then E2 01 40 (loop -> body_base 0x0140, big-endian).
        self.assertEqual(body[-3:], bytes([0xE2, 0x01, 0x40]))

    def test_emit_macro_body_rejects_dac_reg(self):
        from song_packer import emit_macro_body, MacReg, MacEnd, PackError
        with self.assertRaises(PackError):
            emit_macro_body([MacReg(0, 0x2A, 0x00), MacEnd()], body_base=0)

    def test_emit_macro_body_rejects_part(self):
        from song_packer import emit_macro_body, MacReg, MacEnd
        with self.assertRaises(PackError):
            emit_macro_body([MacReg(2, 0x90, 0x00), MacEnd()], body_base=0)

    def test_channel_with_macro_body_emits_nonnull_mod_ptr_and_blob(self):
        # A channel that carries a macro body: pack_song must (a) emit a
        # non-NULL header mod_ptr at the channel's +3/+4, pointing at the
        # body's blob offset, and (b) append the body bytes at that offset.
        from song_packer import MacReg, MacNext, MacEnd
        ch = ChannelDesc(CHROUTE_FM1,
                         [Patch(0), Vol(100), SetDur(0x10),
                          LoopPoint(), Note(57), Jump()])
        ch.macro_body = [MacReg(0, 0x90, 0x08), MacNext(), MacEnd()]
        song = SongDesc(tempo=16, channels=[ch])
        blob = pack_song(song)
        # header: flags,tempo,tempo_base,count, dw pitchtab, then ch record at +6.
        mod_ptr = (blob[6 + 3] << 8) | blob[6 + 4]
        self.assertNotEqual(mod_ptr, 0)
        self.assertEqual(blob[mod_ptr:mod_ptr + 6],
                         bytes([0xE1, 0x00, 0x90, 0x08, 0xE0, 0xE3]))

    def test_channel_without_macro_body_keeps_null_mod_ptr(self):
        # Regression: a normal channel still emits mod_ptr = 0.
        song = _simple_song()
        blob = pack_song(song)
        self.assertEqual((blob[6 + 3] << 8) | blob[6 + 4], 0)

    def test_macro_event_operand_backpatched_to_body(self):
        # A slot[0] Macro() event resolves its 2-byte operand to the same blob
        # offset as the channel's macro body.
        from song_packer import Macro, MacReg, MacNext, MacEnd
        ch = ChannelDesc(CHROUTE_FM1,
                         [Patch(0), Vol(100), SetDur(0x10),
                          LoopPoint(), Macro(), Note(57), Jump()])
        ch.macro_body = [MacReg(0, 0x90, 0x08), MacNext(), MacEnd()]
        song = SongDesc(tempo=16, channels=[ch])
        blob = pack_song(song)
        mod_ptr = (blob[6 + 3] << 8) | blob[6 + 4]
        # find the MEV_MACRO ($F9) byte in the command stream and read its operand.
        cmd_ptr = (blob[6 + 1] << 8) | blob[6 + 2]
        i = blob.index(0xF9, cmd_ptr)
        operand = (blob[i + 1] << 8) | blob[i + 2]
        self.assertEqual(operand, mod_ptr)

    def test_emit_macro_body_loop_without_mac_next_rejected(self):
        # A MacLoop with no MacNext in the body span would cause MacroTick to
        # spin the Z80 forever (hard hang). emit_macro_body must raise PackError.
        from song_packer import emit_macro_body, MacReg, MacLoop, PackError
        with self.assertRaises(PackError) as ctx:
            emit_macro_body([MacReg(0, 0x90, 0x08), MacLoop()], body_base=0)
        self.assertIn("TAG_MAC_NEXT", str(ctx.exception))

    def test_emit_macro_body_loop_with_mac_next_accepted(self):
        # A MacLoop preceded by at least one MacNext is valid.
        from song_packer import emit_macro_body, MacReg, MacNext, MacLoop
        body = emit_macro_body([MacReg(0, 0x90, 0x08), MacNext(), MacLoop()],
                               body_base=0x0200)
        # Should not raise; MacLoop byte present at the end.
        self.assertEqual(body[-3], 0xE2)  # TAG_MAC_LOOP

    def test_emit_macro_body_mac_next_only_no_loop_accepted(self):
        # MacEnd terminator with MacNext present: no hang risk, must be accepted.
        from song_packer import emit_macro_body, MacNext, MacEnd
        body = emit_macro_body([MacNext(), MacEnd()], body_base=0)
        self.assertEqual(body, bytes([0xE0, 0xE3]))

    # --- E3: D8 music-legal route gate ---

    def test_music_song_accepts_expression_opcodes(self):
        # A music channel emitting MEV_PSGENV/$F7/$F8/$F9 must NOT be rejected
        # or silently dropped (D8 music-legal route gate).
        from song_packer import FmEnv, RegWrite, Macro, PsgEnv
        fm = ChannelDesc(CHROUTE_FM1, [
            Patch(0), Vol(100), SetDur(0x10), LoopPoint(),
            FmEnv(2), RegWrite(0, 0x90, 0x08), Macro(),
            Note(0), Jump()])
        psg = ChannelDesc(CHROUTE_PSG1, [
            Vol(90), PsgEnv(3), SetDur(0x10), LoopPoint(), Note(0), Jump()])
        blob = pack_song(SongDesc(tempo=16, channels=[fm, psg]))
        self.assertIn(0xF7, blob)    # MEV_FMENV present, not dropped
        self.assertIn(0xF8, blob)    # MEV_REGWRITE
        self.assertIn(0xF9, blob)    # MEV_MACRO
        self.assertIn(0xEB, blob)    # MEV_PSGENV

    def test_music_illegal_opcode_is_rejected_not_dropped(self):
        # The gate must REJECT (not silently emit) an opcode flagged
        # music-illegal. MEV_SPINREV_RESET ($F1) is dispatch-folded and must
        # never appear in a music stream; pack_song must raise PackError.
        from song_packer import (
            _MUSIC_ILLEGAL_OPCODES, MEV_SPINREV_RESET, Event,
        )
        self.assertIn(MEV_SPINREV_RESET, _MUSIC_ILLEGAL_OPCODES)

        # Synthetic event that encodes to the illegal opcode byte.
        class IllegalEvent(Event):
            def encode(self):
                return bytes([MEV_SPINREV_RESET])

        ch = ChannelDesc(CHROUTE_FM1, [
            Patch(0), Vol(100), SetDur(0x10), LoopPoint(),
            Note(0), IllegalEvent(), Jump()])
        with self.assertRaises(PackError) as ctx:
            pack_song(SongDesc(tempo=16, channels=[ch]))
        self.assertIn(hex(MEV_SPINREV_RESET), str(ctx.exception))

    def test_music_legal_expression_not_in_illegal_set(self):
        # Sanity: the legal expression opcodes ($F7/$F8/$F9/$EB) must NOT be
        # in _MUSIC_ILLEGAL_OPCODES (they are explicitly music-legal).
        from song_packer import (
            _MUSIC_ILLEGAL_OPCODES, _MUSIC_LEGAL_EXPRESSION_OPCODES,
        )
        overlap = _MUSIC_LEGAL_EXPRESSION_OPCODES & _MUSIC_ILLEGAL_OPCODES
        self.assertEqual(overlap, frozenset(),
                         f"legal expression opcodes found in illegal set: {overlap!r}")


class TestConstantsSync(unittest.TestCase):
    """song_packer hand-mirrors the MEV_* opcode and CHROUTE_* route values from
    sound_constants.asm. There is no build-time guard against the two drifting,
    so assert every equate in the .asm matches the Python constant. Fails if
    someone changes a value on only one side.
    """

    @staticmethod
    def _parse_asm_equates():
        # sound_constants.asm sits at the repo root; tests live in <repo>/tools/.
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        asm_path = os.path.join(repo_root, "sound_constants.asm")
        mev, chroute, tag = {}, {}, {}
        # e.g. "MEV_REST        = $80    ; comment"  /  "CHROUTE_FM1 = 0"  /  "TAG_MAC_NEXT = $E0"
        mev_re = re.compile(r"^\s*(MEV_[A-Z0-9_]+)\s*=\s*\$([0-9A-Fa-f]+)")
        chr_re = re.compile(r"^\s*(CHROUTE_[A-Z0-9_]+)\s*=\s*(\d+)")
        tag_re = re.compile(r"^\s*(TAG_MAC_[A-Z0-9_]+)\s*=\s*\$([0-9A-Fa-f]+)")
        with open(asm_path) as f:
            for line in f:
                m = mev_re.match(line)
                if m:
                    mev[m.group(1)] = int(m.group(2), 16)
                    continue
                c = chr_re.match(line)
                if c:
                    chroute[c.group(1)] = int(c.group(2), 10)
                    continue
                t = tag_re.match(line)
                if t:
                    tag[t.group(1)] = int(t.group(2), 16)
        return mev, chroute, tag

    def test_mev_and_chroute_in_sync(self):
        mev, chroute, _tag = self._parse_asm_equates()
        # Sanity: the parse actually found the equates (guards against a moved
        # file or a regex that silently matches nothing).
        self.assertIn("MEV_REST", mev)
        self.assertIn("CHROUTE_DAC", chroute)
        for name, asm_val in {**mev, **chroute}.items():
            py_val = getattr(song_packer, name, None)
            self.assertIsNotNone(
                py_val, f"{name} present in sound_constants.asm but not song_packer.py")
            self.assertEqual(
                py_val, asm_val,
                f"{name}: song_packer.py={py_val} != sound_constants.asm={asm_val}")

    def test_tag_mac_in_sync(self):
        # The slot[1] macro tag bytes must match between the packer emitter and
        # the D-side MacroTick reader (sound_constants.asm TAG_MAC_*), so the
        # bytes can never silently drift. Skip cleanly until the asm equates
        # land (D component) — but once present, every one must mirror.
        _mev, _chroute, tag = self._parse_asm_equates()
        if not tag:
            self.skipTest("TAG_MAC_* equates not yet in sound_constants.asm "
                          "(added by the MacroTick / Component D task)")
        for name, asm_val in tag.items():
            py_val = getattr(song_packer, name, None)
            self.assertIsNotNone(
                py_val, f"{name} in sound_constants.asm but not song_packer.py")
            self.assertEqual(
                py_val, asm_val,
                f"{name}: song_packer.py={py_val} != sound_constants.asm={asm_val}")


if __name__ == "__main__":
    unittest.main()
