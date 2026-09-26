#!/usr/bin/env python3
"""test_psg_song_switch_rule — the stale-latch rule psg_song_switch_witness and
clip_music_witness judge a song switch by (S2CLIP CPZ drone, 2026-09-27).

No emulator. The rule reads a PSG write stream: after a song load (located by the chip
silence Snd_LoadSong writes first), a non-silent attenuation write to a tone channel needs a
divisor write to that channel since the load, and the noise channel a noise-control write;
anything else sounds the previous song's latch.

The fixtures are the Z80's actual PSG bytes around the EHZ -> CPZ switch on the witness route,
recorded from the clip ROM before the fix (s4.s2clip.bin 85ec6e7a, frames 963-966) and after
it: the pre-fix stream must yield exactly the three stale writes that made the drone ($97
PSG1 atten 7, $B7 PSG2 atten 7, $F0 noise atten 0, all before any latch), the post-fix
stream none. The runtime half (the ROM really behaves like the fixture) is the witness in the
keepalive lane; this pins that the rule itself can fail and is not satisfied vacuously.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import psg_song_switch_witness as W     # noqa: E402

# EHZ still playing: PSG1 note (divisor 80), PSG2 note (divisor 190), noise hat
EHZ_TAIL = [(963, 0x80), (963, 0x05), (963, 0x9A), (963, 0xAE), (963, 0x0B), (963, 0xBB),
            (964, 0xC1), (964, 0x00), (964, 0xF2)]
LOAD = [(964, 0x9F), (964, 0xBF), (964, 0xDF), (964, 0xFF)]
CPZ_FIRST_TICK_PREFIX = [(966, 0x97), (966, 0xB7), (966, 0xF0)]      # the pre-fix Vol ops
CPZ_FIRST_TICK = [(966, 0xE7), (966, 0xDF), (966, 0xC1), (966, 0x00), (966, 0xF0),
                  (966, 0xF2), (967, 0xF4)]

BEFORE = EHZ_TAIL + LOAD + CPZ_FIRST_TICK_PREFIX + CPZ_FIRST_TICK
AFTER = EHZ_TAIL + LOAD + CPZ_FIRST_TICK


def _stale(psg, req_frame=964):
    loads = W.locate_loads(psg, [req_frame])
    assert loads == [len(EHZ_TAIL)], loads
    return W.stale_sounds([(i, v) for i, (_f, v) in enumerate(psg)], loads)


def test_the_pre_fix_switch_is_three_stale_sounds():
    got = [(ch, att) for _li, _i, ch, att in _stale(BEFORE)]
    assert got == [(0, 7), (1, 7), (3, 0)]


def test_the_fixed_switch_is_clean():
    assert _stale(AFTER) == []


def test_a_note_latches_before_it_sounds():
    # a tone attack writes the divisor first (Psg_NoteOn -> Psg_EmitDivisor -> PsgEnvAttack)
    psg = LOAD + [(970, 0x85), (970, 0x02), (970, 0x9A)]
    assert W.stale_sounds([(i, v) for i, (_f, v) in enumerate(psg)], [0]) == []
    # the same volume write BEFORE the divisor is stale, even with the divisor right after
    psg = LOAD + [(970, 0x9A), (970, 0x85), (970, 0x02)]
    assert [(c, a) for _l, _i, c, a in
            W.stale_sounds([(i, v) for i, (_f, v) in enumerate(psg)], [0])] == [(0, 10)]


def test_the_latch_set_resets_at_every_load():
    # PSG1 latched after the first load is NOT fresh after the second one
    psg = LOAD + [(970, 0x85), (970, 0x02), (970, 0x9A)] + \
        [(990, v) for _f, v in LOAD] + [(992, 0x98)]
    loads = W.locate_loads(psg, [964, 990])
    assert loads == [0, 7]
    got = W.stale_sounds([(i, v) for i, (_f, v) in enumerate(psg)], loads)
    assert [(li, c, a) for li, _i, c, a in got] == [(1, 0, 8)]


def test_silence_writes_are_never_stale():
    psg = LOAD + [(966, 0x9F), (966, 0xFF)]
    assert W.stale_sounds([(i, v) for i, (_f, v) in enumerate(psg)], [0]) == []


def test_a_switch_that_writes_no_silence_is_a_failure_not_a_skip():
    psg = EHZ_TAIL + CPZ_FIRST_TICK            # no Psg_SilenceAll burst
    loads = W.locate_loads(psg, [964])
    assert loads == [None]
    framed = W.framed_states(psg, 970)
    _lines, fails = W.judge(psg, [(964, 3)], loads, framed, ["cpz"], 970)
    assert len(fails) == 1 and "no PSG silence" in fails[0]


def test_judge_reports_the_drone():
    psg = BEFORE + [(1200, 0xC1), (1200, 0x00), (1200, 0xF2)]
    loads = W.locate_loads(psg, [964])
    framed = W.framed_states(psg, 1200)
    lines, fails = W.judge(psg, [(964, 3)], loads, framed, ["cpz"], 1200)
    assert len(fails) == 3
    assert "PSG1 235 f at atten 7 div 80 (1398.3 Hz)" in lines[0], lines[0]
    assert "PSG2 235 f at atten 7 div 190 (588.7 Hz)" in lines[0], lines[0]
