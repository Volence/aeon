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
    pack_song, emit_asm, PackError,
)

# Route constants mirrored from sound_constants.asm (kept in sync by hand;
# the packer also exposes them).
from song_packer import (
    CHROUTE_FM1, CHROUTE_PSG1, CHROUTE_PSGN, CHROUTE_DAC,
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

    def test_loop_point(self):
        self.assertEqual(LoopPoint().encode(), bytes([0xEE]))

    def test_jump(self):
        self.assertEqual(Jump().encode(), bytes([0xEF]))

    def test_end(self):
        self.assertEqual(End().encode(), bytes([0xFF]))


def _simple_song():
    # 2 channels, both well-formed and looping.
    return SongDesc(tempo=6, channels=[
        ChannelDesc(CHROUTE_FM1, [
            Patch(0), SetDur(0x10), LoopPoint(), Note(57), Rest(), Jump(),
        ]),
        ChannelDesc(CHROUTE_PSG1, [
            SetDur(0x10), LoopPoint(), Note(57), Jump(),
        ]),
    ])


class TestHeader(unittest.TestCase):

    def setUp(self):
        self.song = _simple_song()
        self.blob = pack_song(self.song)

    def test_tempo_and_count(self):
        self.assertEqual(self.blob[0], 6)
        self.assertEqual(self.blob[1], 2)

    def test_channel_routes_and_pointers(self):
        # Header: tempo, count, then per channel (route, dw stream_ptr),
        # then dw patch_table_ptr. Pointers are big-endian offsets within blob.
        off = 2
        ptrs = []
        for ch in self.song.channels:
            self.assertEqual(self.blob[off], ch.route)
            ptr = (self.blob[off + 1] << 8) | self.blob[off + 2]
            ptrs.append(ptr)
            off += 3
        # patch_table_ptr word follows
        off += 2
        # The first stream pointer should point at the first byte after the
        # full header; subsequent ones follow each stream's length.
        header_len = 2 + 3 * len(self.song.channels) + 2
        self.assertEqual(ptrs[0], header_len)
        # Stream 0 bytes equal the encoded events; pointer 1 = ptr0 + len(stream0)
        s0 = b"".join(e.encode() for e in self.song.channels[0].events)
        self.assertEqual(ptrs[1], ptrs[0] + len(s0))
        # The bytes at ptr0 match stream 0.
        self.assertEqual(self.blob[ptrs[0]:ptrs[0] + len(s0)], s0)

    def test_streams_present(self):
        # Concatenated streams appear after the header in order.
        header_len = 2 + 3 * 2 + 2
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

    def test_jump_without_loop_point(self):
        with self.assertRaises(PackError):
            self._pack([ChannelDesc(CHROUTE_FM1, [Note(0), Jump()])])

    def test_unterminated_stream(self):
        with self.assertRaises(PackError):
            self._pack([ChannelDesc(CHROUTE_FM1, [Note(0), Rest()])])

    def test_end_terminator_ok(self):
        # End() is a valid terminator (one-shot, no loop).
        blob = self._pack([ChannelDesc(CHROUTE_FM1, [Note(0), End()])])
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
                          [LoopPoint(), Note(0), Jump()])])
        self.assertIn(0xEF, blob)


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
        mev, chroute = {}, {}
        # e.g. "MEV_REST        = $80    ; comment"  /  "CHROUTE_FM1 = 0"
        mev_re = re.compile(r"^\s*(MEV_[A-Z0-9_]+)\s*=\s*\$([0-9A-Fa-f]+)")
        chr_re = re.compile(r"^\s*(CHROUTE_[A-Z0-9_]+)\s*=\s*(\d+)")
        with open(asm_path) as f:
            for line in f:
                m = mev_re.match(line)
                if m:
                    mev[m.group(1)] = int(m.group(2), 16)
                    continue
                c = chr_re.match(line)
                if c:
                    chroute[c.group(1)] = int(c.group(2), 10)
        return mev, chroute

    def test_mev_and_chroute_in_sync(self):
        mev, chroute = self._parse_asm_equates()
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


if __name__ == "__main__":
    unittest.main()
