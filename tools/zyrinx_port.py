#!/usr/bin/env python3
"""zyrinx_port — transcode the decoded "Moving Trucks" (The Adventures of Batman
& Robin, Zyrinx "Advanced Z80 Player", music Jesper Kyd) into our v0 music
format (a song_packer SongDesc).

This is BUILD-PC tooling: it reads the already-decoded song JSON
(`megadaw_export/05_Moving_Trucks.json`) and emits an AS data file the engine
includes. No driver code is ported — only data is translated.

----------------------------------------------------------------------------
Mapping decisions (Sound 1D Task 1; calibrated against the reference VGM in T5)
----------------------------------------------------------------------------

NOTE.  Zyrinx note values are MIDI-style (octave = note//12, semitone =
note%12).  Our pitch index = MIDI - 12 (semitone 0 = C0).  The decoded JSON
already carries raw note values; the candidate calibration is "Zyrinx note 0 =
C0 = MIDI 12 = our index 0", i.e. our index == note value.  OCTAVE_BASE_OFFSET
captures any whole-octave correction T5 finds against the VGM; it is 0 now.
  our_pitch = note + pattern.pitch_transpose + OCTAVE_BASE_OFFSET, clamped 0..0x5E.

TEMPO.  Moving Trucks format code = 56 ($38) -> 60*16/56 ~= 17.14 events/sec.
Our tick clock is YM Timer A: N = tempo<<2, period = 18.773us*(1024-N), rate =
1/period.  At tempo 0 (N=0) the rate is ALREADY ~52 Hz — Timer A CANNOT tick as
slowly as 17 Hz (its floor is ~52 Hz).  So the tempo byte pins to the floor (0)
and wall-clock fidelity comes from the DURATION_SCALE factor below.  (T5 may
re-pin both against the VGM onset timing.)

DURATION.  The decoder resolved each `wait` into `frames` = the number of
original event-slots the note/rest is held.  One original event-slot ~= 1/17.14
sec; our tick ~= 1/52 sec.  So a frame spans DURATION_SCALE = round(52/17.14) =
3 of our ticks.  our_dur = frames * DURATION_SCALE (notes use NoteDur, dur<=255;
the largest wait is 63 frames -> 189 <= 255, fits).

STRUCTURE.  Fully unrolling the repeats is ~50,900 events (~100KB).  Instead each
pattern's sequence body is emitted ONCE wrapped in MEV_REPEAT_START..
MEV_REPEAT_END(repeat) so the song stays ~8KB.  Each channel is wrapped in
LoopPoint()..Jump() (song header loop_point = 0 -> loop the whole pattern list).

CHANNELS.  The JSON's channels[] 16-per-channel split is approximate (the real
per-YM-voice assignment was set by the game's 68K loader, not in the song
binary).  T1 uses channels[] as-is: ch0-5 are the 6 active FM voices, ch6 is a
1-pattern stub (DROPPED + logged).  We have only 5 sequencer FM routes today
(FM1..FM5); the 6th FM voice (ch5) is HELD ASIDE for T3's adaptive FM6 slot.  So
T1 ships ch0-4 -> FM1..FM5; ch5 is logged as deferred.

VOICES / PAN / VOLUME.  T1 stubs voices to Patch(0) (a leading setup patch so the
packer accepts the FM channel) and DROPS pan/volume/fm_op/flag/ch_select events.
Real voice translation is T2; pan + volume dynamics are T4.
"""

import json
import sys


# --- Calibration constants (pinned now; T5 re-calibrates against the VGM) ---
OCTAVE_BASE_OFFSET = 0           # whole-octave correction (note == our index)
DURATION_SCALE = 3               # our ticks per original frame (~52/17.14)
ZYRINX_FORMAT_MOVING_TRUCKS = 56  # header format code ($38)

# Our pitch index range (mirror of song_packer.MAX_PITCH = MEV_NOTE_MAX-BASE).
MAX_PITCH = 0x5E

# Our v0 NoteDur duration field is a single byte.
MAX_DUR = 0xFF

# Timer-A constants for the tempo math (mirror sound_constants.asm).
_TIMERA_PERIOD_NS = 18773         # 18.773 us per Timer-A count tick (NTSC)


# Import the packer event helpers. Support both `import zyrinx_port` (tools/ on
# path) and `from tools import zyrinx_port` styles.
try:
    from song_packer import (
        SongDesc, ChannelDesc,
        Note, NoteDur, Rest, SetDur, Patch, Vol, LoopPoint, Jump,
        RepeatStart, RepeatEnd,
        CHROUTE_FM1, CHROUTE_FM5,
    )
except ImportError:  # pragma: no cover - alternate import path
    from tools.song_packer import (  # type: ignore
        SongDesc, ChannelDesc,
        Note, NoteDur, Rest, SetDur, Patch, Vol, LoopPoint, Jump,
        RepeatStart, RepeatEnd,
        CHROUTE_FM1, CHROUTE_FM5,
    )


# --- Pure mapping functions ------------------------------------------------

def zyrinx_note_to_pitch(note: int, transpose: int = 0,
                         offset: int = OCTAVE_BASE_OFFSET) -> int:
    """Zyrinx note value -> our pitch index, clamped to 0..MAX_PITCH.

    our_pitch = note + transpose + offset (offset defaults to the pinned
    OCTAVE_BASE_OFFSET). Identity when transpose/offset are 0.
    """
    p = note + transpose + offset
    if p < 0:
        return 0
    if p > MAX_PITCH:
        return MAX_PITCH
    return p


def _timera_rate_hz(tempo_byte: int) -> float:
    """YM Timer-A overflow rate for a tempo byte (N = tempo<<2)."""
    n = tempo_byte << 2
    period_ns = (1024 - n) * _TIMERA_PERIOD_NS
    return 1e9 / period_ns


def zyrinx_tempo_to_byte(format_code: int, tempo_delta: int = 0) -> int:
    """Zyrinx format code (+ optional pattern tempo_delta) -> our Timer-A tempo
    byte, chosen so our tick rate is as close as Timer A can get to the
    original's events/sec.

    events/sec = 60*16 / (format_code + tempo_delta)  (Zyrinx; +delta = slower).
    Timer-A rate floor is ~52 Hz (tempo 0), so a slow song like Moving Trucks
    (~17 Hz) pins to the floor; DURATION_SCALE makes up the wall-clock timing.
    """
    base = format_code + tempo_delta
    if base <= 0:
        base = 1
    target_hz = (60 * 16) / base
    best_byte, best_err = 0, None
    for tb in range(0, 256):
        err = abs(_timera_rate_hz(tb) - target_hz)
        if best_err is None or err < best_err:
            best_byte, best_err = tb, err
    return best_byte


def wait_to_dur(frames: int) -> int:
    """Zyrinx `wait` frame count -> our duration ticks (frames * DURATION_SCALE,
    clamped to the NoteDur byte range)."""
    d = frames * DURATION_SCALE
    if d > MAX_DUR:
        return MAX_DUR
    if d < 0:
        return 0
    return d


# --- Loading + flattening --------------------------------------------------

def load_song(json_path: str) -> dict:
    """Load the decoded Moving Trucks JSON (the transcoder input)."""
    with open(json_path) as f:
        return json.load(f)


def _flatten_sequence_body(seq: dict, transpose: int) -> list:
    """Translate ONE resolved sequence's events into v0 events (the body that a
    RepeatStart/RepeatEnd wraps).

    Model (validated against the decoded data): events come in
    [pitch, voice?, fm_op*, wait] groups. `pitch` sets the pending note; the
    following `wait frames=N` emits NoteDur(pitch, N) (or Rest if no pitch is
    pending). T1 drops voice/pan/volume/fm_op/flag/ch_select. The `loop` event
    terminates the body (we stop consuming there).
    """
    out = []
    pending = None          # pending pitch index awaiting its wait duration
    clamps = 0
    for ev in seq["events"]:
        t = ev["type"]
        if t in ("pitch", "note"):
            # Single-pitch only in Moving Trucks (no chords). Take pitch[0].
            raw = ev["pitches"][0]
            mapped = zyrinx_note_to_pitch(raw, transpose)
            if (raw + transpose + OCTAVE_BASE_OFFSET) != mapped:
                clamps += 1
            pending = mapped
        elif t == "wait":
            dur = wait_to_dur(ev["frames"])
            if pending is not None:
                out.append(NoteDur(pending, dur))
                pending = None
            else:
                # No active note -> a rest for this duration.
                out.append(SetDur(min(dur, 0x7F)))
                out.append(Rest())
        elif t == "loop":
            break               # body terminator
        else:
            # voice / pan / volume / fm_op / flag / ch_select / param / reset /
            # ch_off — all dropped in T1 (voices -> T2, pan/vol -> T4).
            continue
    return out, clamps


def flatten_channel(channel: dict, sequences: dict, route: int) -> list:
    """Flatten one JSON channel into a v0 event list:
        [Patch(0), Vol(100),]?  LoopPoint, (RepeatStart, body, RepeatEnd(n))*, Jump

    FM routes get a leading Patch(0)+Vol(100) setup (voices are stubbed in T1)
    so the packer's "FM keys a note before Patch+Vol" guard is satisfied.
    """
    events = []
    is_fm = (CHROUTE_FM1 <= route <= CHROUTE_FM5)
    if is_fm:
        events.append(Patch(0))     # T1 placeholder voice (real voices in T2)
        events.append(Vol(100))     # T1 placeholder volume (real dynamics in T4)
    events.append(LoopPoint())

    total_clamps = 0
    for pat in channel["patterns"]:
        seq_idx = str(pat["seq_idx"])
        seq = sequences.get(seq_idx)
        if seq is None:
            print(f"  [warn] ch{channel.get('channel_idx')}: missing "
                  f"sequence {seq_idx} — skipped", file=sys.stderr)
            continue
        body, clamps = _flatten_sequence_body(seq, pat["pitch_transpose"])
        total_clamps += clamps
        if not body:
            continue                # empty body — nothing to repeat
        repeat = pat["repeat"]
        if not (1 <= repeat <= 255):
            print(f"  [warn] ch{channel.get('channel_idx')}: repeat {repeat} "
                  f"out of range 1..255 — clamped", file=sys.stderr)
            repeat = max(1, min(255, repeat))
        events.append(RepeatStart())
        events.extend(body)
        events.append(RepeatEnd(repeat))

    events.append(Jump())
    if total_clamps:
        print(f"  [info] ch{channel.get('channel_idx')}: {total_clamps} "
              f"pitch value(s) clamped to 0..0x{MAX_PITCH:X}", file=sys.stderr)
    return events


# ch0-4 -> FM1..FM5. ch5 is the 6th FM voice held aside for T3's adaptive FM6.
# ch6 is a 1-pattern stub (dropped). Indices beyond 4 are not routed in T1.
_T1_FM_ROUTES = [CHROUTE_FM1, CHROUTE_FM1 + 1, CHROUTE_FM1 + 2,
                 CHROUTE_FM1 + 3, CHROUTE_FM5]


def build_songdesc(raw: dict) -> SongDesc:
    """Turn the loaded JSON into a packer-accepted SongDesc.

    Routes ch0-4 -> FM1..FM5. ch5 (the 6th FM voice) is DEFERRED to T3 (we have
    no FM6 route yet). ch6 (the 1-pattern stub) is DROPPED + logged.
    """
    tempo = zyrinx_tempo_to_byte(raw["header"]["format"])
    sequences = raw["sequences"]
    channels = []
    for i, ch in enumerate(raw["channels"]):
        npat = len(ch.get("patterns", []))
        if i >= len(_T1_FM_ROUTES):
            # ch5 = 6th FM voice (FM6, T3); ch6 = trivial stub (drop).
            reason = ("FM6 — deferred to T3 (adaptive FM6 slot)"
                      if i == 5 else "trivial stub — dropped")
            print(f"  [info] ch{i} ({npat} pattern(s)) NOT routed in T1: "
                  f"{reason}", file=sys.stderr)
            continue
        events = flatten_channel(ch, sequences, _T1_FM_ROUTES[i])
        channels.append(ChannelDesc(_T1_FM_ROUTES[i], events))
    return SongDesc(tempo=tempo, channels=channels)


# --- CLI: regenerate the .asm ----------------------------------------------

def main(argv=None):
    import argparse
    try:
        from song_packer import write_asm
    except ImportError:  # pragma: no cover
        from tools.song_packer import write_asm  # type: ignore

    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser(description="Transcode Moving Trucks -> v0 song")
    ap.add_argument("json", help="path to 05_Moving_Trucks.json")
    ap.add_argument("out", help="output .asm path")
    ap.add_argument("--label", default="Song_MovingTrucks")
    args = ap.parse_args(argv)

    raw = load_song(args.json)
    song = build_songdesc(raw)
    write_asm(song, args.label, args.out)
    # Report the emitted size.
    try:
        from song_packer import pack_song
    except ImportError:  # pragma: no cover
        from tools.song_packer import pack_song  # type: ignore
    size = len(pack_song(song))
    print(f"wrote {args.out}: {len(song.channels)} channel(s), {size} bytes "
          f"(tempo ${song.tempo:02X})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
