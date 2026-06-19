#!/usr/bin/env python3
"""Tests for zyrinx_player — native B&R "Moving Trucks" (Bank2 song4) transcoder.

Focus: walk_body's EVENT-TICK ACCOUNTING under the Zyrinx two-table dispatch.

The desync bug: walk_body did not model the driver's Table-1/Table-2 dispatch or
the Table-2-NOTE orphan-tick rewind (NoteTrigger $0A60: DEC HL, re-read the note
next tick as a Table-1 PITCH). The dense fast lines (seq117/113/121) are cells
like `GATE WAIT$FF | PITCH WAIT$FF | GATE [NOTE->rewind] ...`; the real driver
fuses each orphan so the onset cadence is one key-on per 2 event-ticks and the
body spans 64 event-ticks. The bug charged every WAIT$FF group as its own 1-tick
onset -> body ~34 ticks -> the channel runs ~1.9x too fast and drifts off the
shared grid (verified against the live B&R oracle capture: fast channels onset
every 7 frames = 2 event-ticks; melody every 14 frames = 4 event-ticks).

The loop-unit invariant: a channel that is meant to stay phase-locked to the
melody must have a body whose total event-tick length matches. seq115 (melody,
4-tick notes) and seq117 (fast line) are both 64 event-ticks in the real engine;
the bug only breaks seq117.

Run: python3 -m unittest tools.test_zyrinx_player
"""

import os
import sys
import unittest
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from zyrinx_player import _Walker, parse_song, seq_addr, ROM_PATH
from song_packer import SetDur, Rest, Note, NoteDur, NoteRaw, PitchEnv


# A neutral voice so _Walker._voice (VOICE $18 handling) works without the real
# Bank2 voice table — VOICE is a zero-tick setter and does not affect tick count.
_NEUTRAL_VOICE = {
    "fb": 0, "algo": 0, "dt_mul": [0, 0, 0, 0], "tl": [0, 0, 0, 0],
    "ks_ar": [0, 0, 0, 0], "am_d1r": [0, 0, 0, 0], "d2r": [0, 0, 0, 0],
    "sl_rr": [0, 0, 0, 0], "ams_fms_pan": 0xC0, "ext": [0, 0, 0, 0],
}


class _AnyBank:
    def __getitem__(self, k):
        return _NEUTRAL_VOICE


class _ZeroRemap:
    def __getitem__(self, k):
        return 0


def body_ticks(events):
    """Total event-ticks an emitted body occupies (the loop-unit length): each
    time-advancing event consumes the current SetDur (PitchEnv/Rest/Note) or its
    own explicit dur (NoteDur/NoteRaw)."""
    total = 0
    cur = 0
    for e in events:
        if isinstance(e, SetDur):
            cur = e.ticks
        elif isinstance(e, (PitchEnv, Rest, Note)):
            total += cur
        elif isinstance(e, (NoteDur, NoteRaw)):
            total += e.dur
    return total


def onset_positions(events):
    """Event-tick position of every key-on (PitchEnv/Note/NoteDur/NoteRaw)."""
    pos = []
    t = 0
    cur = 0
    for e in events:
        if isinstance(e, SetDur):
            cur = e.ticks
        elif isinstance(e, (PitchEnv, Note)):
            pos.append(t)
            t += cur
        elif isinstance(e, NoteDur):
            pos.append(t)
            t += e.dur
        elif isinstance(e, NoteRaw):
            pos.append(t)
            t += e.dur
        elif isinstance(e, Rest):
            t += cur
    return pos


# Expected per-body event-tick length under the faithful Zyrinx two-table model
# (derived by tracing the real ROM bytes; cross-checked against the live oracle
# capture: every body is 64 event-ticks so all channels share a 2688-tick loop
# and stay phase-locked; seq22 is the 32-tick intro pad, played x2).
EXPECTED_BODY_TICKS = {
    115: 64, 110: 64, 113: 64, 122: 64, 111: 64, 114: 64, 118: 64, 123: 64,
    117: 64, 22: 32, 120: 64, 112: 64, 116: 64, 119: 64, 121: 64,
}


@unittest.skipUnless(os.path.exists(ROM_PATH), "B&R ROM not present")
class TestWalkBodyTickAccounting(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(ROM_PATH, "rb") as f:
            cls.rom = f.read()
        cls.chans = parse_song(cls.rom)

    def _walk(self, seq_idx, transpose=0):
        w = _Walker(self.rom, _AnyBank(), _ZeroRemap(), defaultdict(int))
        return w.walk_body(seq_addr(self.rom, seq_idx), transpose)

    def test_source_seq_indices_match_known_song(self):
        # Documents the data this test relies on (from the disasm diagnosis):
        # ch0 entry0 = seq115 (melody), ch2 entry0 = seq117 (fast line).
        self.assertEqual(self.chans[0]["entries"][0]["seq"], 115)
        self.assertEqual(self.chans[2]["entries"][0]["seq"], 117)

    def test_melody_body_seq115_is_64_ticks(self):
        # Regression guard: the melody (PITCH + WAIT$FC, 4 ticks/note) is already
        # correct and must stay 64 event-ticks per loop iteration.
        e0 = self.chans[0]["entries"][0]
        ev = self._walk(e0["seq"], e0["transpose"])
        self.assertEqual(body_ticks(ev), 64)

    def test_fast_body_seq117_is_64_ticks(self):
        # THE BUG: the dense GATE/PITCH/orphan fast line must span 64 event-ticks
        # (orphan-tick rewind -> onset every 2 ticks), not ~34. A 34-tick body is
        # ~1.9x too fast and races ahead of the 64-tick melody (the desync).
        e0 = self.chans[2]["entries"][0]
        ev = self._walk(e0["seq"], e0["transpose"])
        self.assertEqual(body_ticks(ev), 64)

    def test_all_referenced_bodies_match_auth(self):
        # The decisive sync invariant: EVERY sequence the song references must
        # emit a body of the AUTH event-tick length, so all channels share the
        # same 2688-tick loop and never drift apart.
        seen = set()
        for c in self.chans:
            for e in c["entries"]:
                s = e["seq"]
                if s in seen:
                    continue
                seen.add(s)
                ev = self._walk(s, e["transpose"])
                self.assertEqual(body_ticks(ev), EXPECTED_BODY_TICKS[s],
                                 f"seq{s} body length")

    def test_fast_body_onset_cadence(self):
        # Faithful cadence: the fast line keys on ~once per 2 event-ticks (PITCH
        # tick + orphan re-arm tick) — 33 onsets across the 64-tick body, with
        # only the dominant 2-tick spacing (and at most a 1-tick edge gap; never
        # the >=4-tick gaps the coalescing bug produced).
        e0 = self.chans[2]["entries"][0]
        ev = self._walk(e0["seq"], e0["transpose"])
        onsets = onset_positions(ev)
        self.assertEqual(len(onsets), 33)
        spacings = [b - a for a, b in zip(onsets, onsets[1:])]
        self.assertTrue(set(spacings) <= {1, 2},
                        f"unexpected onset spacings: {sorted(set(spacings))}")
        self.assertEqual(max(spacings, key=spacings.count), 2)


@unittest.skipUnless(os.path.exists(ROM_PATH), "B&R ROM not present")
class TestPitchTable(unittest.TestCase):
    """The hand-transcribed §2.4 pitch table must map the song's bass indices to the
    oracle's exact notes: $1C/$28/$34/$40 -> C1/C2/C3/C4 (block0..2, fnum 645/1290).
    (Guards against swapping in the $1E7000 ROM table, which holds the same fnum
    value-SET but shifted ~4 semitones at these indices = everything plays flat.)"""

    EXPECTED = {
        0x1C: (0, 645),    # C1
        0x28: (0, 1290),   # C2
        0x34: (1, 1290),   # C3
        0x40: (2, 1290),   # C4
    }

    def test_bass_indices_map_to_oracle_C_notes(self):
        from zyrinx_player import BLOCK_TBL, FNUM_TBL
        for idx, (blk, fnum) in self.EXPECTED.items():
            self.assertEqual((BLOCK_TBL[idx], FNUM_TBL[idx]), (blk, fnum),
                             f"pitch idx ${idx:02X}")


@unittest.skipUnless(os.path.exists(ROM_PATH), "B&R ROM not present")
class TestOpBiasReset(unittest.TestCase):
    """The Zyrinx driver clears op_mod (the per-operator TL bias) at EVERY
    ChannelReset = pattern/loop boundary ($044F clears IX+9/11/13/15). Our
    per-pattern bodies must do the same: each body (right after its RepeatStart)
    must reset all 4 OpBias operators to 0 BEFORE any note. Otherwise a prior
    pattern's bias leaks into the next voice -- e.g. seq123 sets OP1-4=$0F (the
    'higher note' ~12 measures in) and the bass that follows (seq114) only resets
    OP2, so OP1/OP3/OP4 stay biased and the bass comes back wrong (user-reported)."""

    def test_each_body_resets_all_opbias(self):
        from zyrinx_player import build_native_songdesc
        from song_packer import (OpBias, RepeatStart, PitchEnv, Note, Rest,
                                  NoteDur, NoteRaw)
        with open(ROM_PATH, "rb") as f:
            rom = f.read()
        song, _, _ = build_native_songdesc(rom)
        ADV = (PitchEnv, Note, Rest, NoteDur, NoteRaw)
        for ci, c in enumerate(song.channels):
            ev = c.events
            for i, e in enumerate(ev):
                if isinstance(e, RepeatStart):
                    cleared = set()
                    for e2 in ev[i + 1:]:
                        if isinstance(e2, ADV):
                            break
                        if isinstance(e2, OpBias) and e2.val == 0:
                            cleared.add(e2.op)
                    self.assertEqual(
                        cleared, {0, 1, 2, 3},
                        f"ch{ci} body at event {i}: opbias not fully reset "
                        f"before first note (cleared ops {sorted(cleared)})")


if __name__ == "__main__":
    unittest.main()
