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
class TestBodyPrefixThinning(unittest.TestCase):
    """The body-boundary micro-pause fix (_thin_body_prefixes): the naive emission
    replayed a full state-reset prefix — OpBias(0)x4 + a full ~26-write Patch +
    NoteFill — on ALL SIX channels in the single sequencer tick of every pattern
    boundary (~226 chip writes at the worst one), overrunning the 16.7 ms frame
    by 25-42 ms so every channel's next note keyed late (the audible pause right
    before measure 5, ~3.7 s). The thinned emission keeps only the prefix events
    whose state actually changes.

    Two invariants, BOTH verified against the naive build across TWO loop passes
    (the loop seam re-enters body 0 with the FINAL body's exit state, and
    RepeatEnd re-enters a body with its OWN exit state — a prefix may be thinned
    only if it is redundant in every one of those scenarios):

    1. EQUIVALENCE — at every key-on the musical + engine state is identical:
       tick, pitch points, duration, active voice bytes, NoteFill, the OpBias
       state latched at key-on AND at the last patch load (the engine applies
       biases to modulator TLs only at patch load — Fm_PatchTlGroup — which is
       why an emitted bias reset always forces the full Patch). This subsumes
       the old all-4-resets check: ChannelReset parity ($044F clears op_mod at
       every pattern boundary; e.g. seq123 leaves OP1-4=$0F and the following
       bass seq114 only resets OP2) holds because the naive build resets
       everything and the states still match.

    2. BUDGET — no event tick in the whole stream bursts past the write budget,
       so the boundary stall cannot regress silently."""

    # Per-tick chip-write budget (simulate_write_bursts weights): the thinned
    # stream's worst mid-song tick measures 208 (genuine simultaneous instrument
    # changes at a section boundary); 224 adds margin while still failing the
    # naive emission (236 at the measure-5 boundary, 242-244 at others).
    WRITE_BUDGET = 224
    # Tick 0 is exempt up to this: song start pays the 6-channel leading setup
    # (Patch+Vol) PLUS body 0's loop-guard prefix (~366 writes). Nothing is
    # sounding yet and all channels start together, so a late first tick is a
    # uniform start offset, not an audible stall.
    START_TICK_BUDGET = 400

    @classmethod
    def setUpClass(cls):
        from zyrinx_player import build_native_songdesc
        from zyrinx_port import FMPATCH_LEN
        with open(ROM_PATH, "rb") as f:
            rom = f.read()
        cls.naive, _, _ = build_native_songdesc(
            rom, suppress_redundant_state=False)
        cls.thinned, _, (bank, _, pcount) = build_native_songdesc(rom)
        cls.recs = [bytes(bank[i * FMPATCH_LEN:(i + 1) * FMPATCH_LEN])
                    for i in range(pcount)]

    def _keyon_trace(self, song, loops=2):
        """Per channel: the (tick, pitch points, dur, voice bytes, fill,
        bias@keyon, bias@last-patch-load, pan, vol) tuple of every key-on across
        `loops` loop passes of the expanded stream."""
        from zyrinx_player import expand_channel_stream
        from song_packer import (SetDur, Rest, Vol, Patch, Pan, OpBias,
                                 PitchEnv, RegDelta, NoteFill,
                                 REGDELTA_GROUP_SHIFT, REGDELTA_OP_MASK)
        traces = []
        for c in song.channels:
            tr = []
            t = 0
            cur = 0
            fp = None                      # active voice's FmPatch bytes
            fill = 0                       # engine channel-reset default
            bias = [0, 0, 0, 0]
            bias_at_load = (0, 0, 0, 0)    # sc_opbias when the patch last loaded
            pan = None
            vol = None
            for e in expand_channel_stream(c.events, loops=loops):
                if isinstance(e, SetDur):
                    cur = e.ticks
                elif isinstance(e, Patch):
                    fp = bytearray(self.recs[e.patch])
                    bias_at_load = tuple(bias)
                elif isinstance(e, RegDelta):
                    for rs, val in e.entries:
                        group = (rs >> REGDELTA_GROUP_SHIFT) & 0x0F
                        op = rs & REGDELTA_OP_MASK
                        fp[2 + group * 4 + op] = val & 0xFF
                elif isinstance(e, OpBias):
                    bias[e.op] = e.val
                elif isinstance(e, NoteFill):
                    fill = e.master
                elif isinstance(e, Pan):
                    pan = e.b4
                elif isinstance(e, Vol):
                    vol = e.vol
                elif isinstance(e, PitchEnv):
                    tr.append((t, tuple(e.points), cur,
                               bytes(fp) if fp is not None else None,
                               fill, tuple(bias), bias_at_load, pan, vol))
                    t += cur
                elif isinstance(e, Rest):
                    t += cur
            traces.append(tr)
        return traces

    def test_keyon_state_equivalence_across_loop(self):
        tn = self._keyon_trace(self.naive)
        tt = self._keyon_trace(self.thinned)
        for ci, (a, b) in enumerate(zip(tn, tt)):
            self.assertEqual(len(a), len(b), f"ch{ci} key-on count changed")
            for i, (x, y) in enumerate(zip(a, b)):
                self.assertEqual(x, y, f"ch{ci} key-on {i} state differs "
                                       f"(naive {x} vs thinned {y})")

    def test_write_burst_budget(self):
        from zyrinx_player import simulate_write_bursts
        cost = simulate_write_bursts(self.thinned, loops=2)
        self.assertLessEqual(cost.get(0, 0), self.START_TICK_BUDGET,
                             "song-start tick over budget")
        worst_t, worst = max(((t, w) for t, w in cost.items() if t > 0),
                             key=lambda kv: kv[1])
        self.assertLessEqual(
            worst, self.WRITE_BUDGET,
            f"tick {worst_t} bursts {worst} chip writes (> "
            f"{self.WRITE_BUDGET}) — a body-boundary prefix regressed; the "
            f"naive emission stalled 25-42 ms at such ticks (audible pause)")

    def test_measure5_boundary_thinned(self):
        # The user-audible boundary: tick 64 (~3.7 s, the intro's 32x2 ticks
        # ending where FM4's high run starts) burst ~236 writes naive; thinned
        # it must stay near just-the-keyons + the two GENUINE instrument
        # changes that enter there.
        from zyrinx_player import simulate_write_bursts
        naive = simulate_write_bursts(self.naive, loops=2)
        thinned = simulate_write_bursts(self.thinned, loops=2)
        self.assertGreaterEqual(naive.get(64, 0), 200)   # documents the bug
        self.assertLessEqual(thinned.get(64, 0), 120)    # and the fix


@unittest.skipUnless(os.path.exists(ROM_PATH), "B&R ROM not present")
class TestChannelVolume(unittest.TestCase):
    """Moving Trucks emits NO source VOL commands ($0A-$12), so the channel volume
    must be the driver default = FULL (Vol 127), which adds 0 carrier attenuation
    (LogVolumeLut[127]=0). The dynamics come from voice-stepping, not a volume
    envelope. A fixed Vol(110) added +4 attenuation to every carrier (LogVolumeLut
    [110]=4) -> the kick lost its punch (verified vs the oracle: B&R FM2 carriers
    sit at base TL 0/1, ours were +4)."""

    def test_leading_volume_is_full(self):
        from zyrinx_player import build_native_songdesc
        from song_packer import Vol
        with open(ROM_PATH, "rb") as f:
            rom = f.read()
        song, _, _ = build_native_songdesc(rom)
        for ci, c in enumerate(song.channels):
            vols = [e.vol for e in c.events if isinstance(e, Vol)]
            self.assertTrue(vols, f"ch{ci} has no Vol event")
            self.assertEqual(vols[0], 127, f"ch{ci} leading volume not full")


@unittest.skipUnless(os.path.exists(ROM_PATH), "B&R ROM not present")
class TestNoteFill(unittest.TestCase):
    """#4 gate articulation: NoteFill(n)/NoteFill(0) is emitted at voice changes so
    that every keyed note plays with the gate the reference (mt_ref.vgm) uses for
    its (channel, voice) bucket — see zyrinx_player.NATIVE_GATE_TABLES. Replaces
    the old blanket FM6-wide NoteFill, which leaked onto FM6's held melodic stabs
    (1.89 s in the reference) and truncated them at 3 frames."""

    @staticmethod
    def _fingerprint(rec):
        """FmPatch record -> the gate-table voice identity (alg_fb, dt_mul[4])."""
        return (rec[0], tuple(rec[2:6]))

    def test_fill_matches_gate_table_at_every_note(self):
        # Replay each channel's event stream tracking the active voice (Patch /
        # RegDelta) and the active NoteFill; at every keyed note (PitchEnv) the
        # active fill must equal the channel's gate-table value for the active
        # voice. This is the data-level guarantee that the emitted stream plays
        # the reference's per-(channel, voice) duty profile.
        from zyrinx_player import build_native_songdesc, NATIVE_GATE_TABLES
        from zyrinx_port import FMPATCH_LEN
        from song_packer import NoteFill, Patch, RegDelta, PitchEnv
        with open(ROM_PATH, "rb") as f:
            rom = f.read()
        song, _, (bank_bytes, _remap, pcount) = build_native_songdesc(rom)
        recs = [bytearray(bank_bytes[i * FMPATCH_LEN:(i + 1) * FMPATCH_LEN])
                for i in range(pcount)]
        seen_fills = set()
        for ci, c in enumerate(song.channels):
            table = NATIVE_GATE_TABLES[ci]
            state = None          # active voice's FmPatch bytes (mutable copy)
            fill = 0              # engine default after channel reset = legato
            armed = False         # a body VOICE has run (fill is voice-accurate)
            for e in c.events:
                if isinstance(e, Patch):
                    state = bytearray(recs[e.patch])
                elif isinstance(e, RegDelta) and state is not None:
                    for rs, val in e.entries:
                        group, op = rs >> 2, rs & 3
                        state[2 + group * 4 + op] = val & 0xFF
                elif isinstance(e, NoteFill):
                    fill = e.master
                    seen_fills.add(e.master)
                    armed = True
                elif isinstance(e, PitchEnv) and state is not None and armed:
                    want = table.get(self._fingerprint(state), 0)
                    self.assertEqual(
                        fill, want,
                        "ch%d: note under voice %s plays fill %d, gate table "
                        "says %d" % (ci, self._fingerprint(state), fill, want))
        # The profile actually exercises the gates (not vacuously legato):
        # 8 = bass "bonk" (8 of 14 frames), 5 = fast-run choke (5 of 7 frames),
        # 17 = downbeat bass (legato on its 14-frame slots, 17 of 21 on the long
        # ones), 0 = explicit return to legato (protects FM6's held stabs).
        self.assertEqual(seen_fills, {0, 5, 8, 17})

    def test_every_channel_returns_to_legato_somewhere(self):
        # Each MT channel mixes gated and legato voices, so every stream must
        # contain BOTH a non-zero NoteFill and a NoteFill(0) (the FM6 melodic
        # sections in particular must not inherit the percussion gate).
        from zyrinx_player import build_native_songdesc
        from song_packer import NoteFill
        with open(ROM_PATH, "rb") as f:
            rom = f.read()
        song, _, _ = build_native_songdesc(rom)
        for ci, c in enumerate(song.channels):
            masters = [e.master for e in c.events if isinstance(e, NoteFill)]
            self.assertTrue(any(m > 0 for m in masters),
                            "ch%d has no gated voice" % ci)
            self.assertTrue(any(m == 0 for m in masters),
                            "ch%d never returns to legato" % ci)


@unittest.skipUnless(os.path.exists(ROM_PATH), "B&R ROM not present")
class TestOpBiasBeforePatch(unittest.TestCase):
    """The engine applies the per-operator TL bias (OpBias -> sc_opbias) DURING the
    patch load (Fm_PatchTlGroup: TL = patch_TL + sc_opbias), so any OpBias for a
    note must be emitted BEFORE that note's Patch/RegDelta. If a Patch loads first,
    the note's operator levels omit the bias (wrong modulator/carrier TL -> wrong
    timbre, lost kick punch). Matches the driver's key-on TL = (0x7F^patch_TL)+op_mod.
    Invariant: within a group (between time-advancing events), no OpBias follows a
    Patch/RegDelta."""

    def test_opbias_precedes_patch_in_each_group(self):
        from zyrinx_player import build_native_songdesc
        from song_packer import (OpBias, Patch, RegDelta, PitchEnv, Note, Rest,
                                  NoteDur, NoteRaw, RepeatStart)
        with open(ROM_PATH, "rb") as f:
            rom = f.read()
        song, _, _ = build_native_songdesc(rom)
        ADV = (PitchEnv, Note, Rest, NoteDur, NoteRaw)
        for ci, c in enumerate(song.channels):
            seen_patch = False
            for e in c.events:
                # group boundaries: a time-advancing event ends a note's group, and
                # RepeatStart begins a body (the leading channel Patch lives before
                # the first RepeatStart and is not part of any note's group).
                if isinstance(e, ADV) or isinstance(e, RepeatStart):
                    seen_patch = False
                elif isinstance(e, (Patch, RegDelta)):
                    seen_patch = True
                elif isinstance(e, OpBias) and seen_patch:
                    self.fail(f"ch{ci}: OpBias(op{e.op},{e.val}) emitted AFTER a "
                              f"Patch/RegDelta in the same group (bias will be lost)")


if __name__ == "__main__":
    unittest.main()
