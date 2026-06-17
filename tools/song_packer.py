#!/usr/bin/env python3
"""song_packer — build-time music song description -> packed bytes + .asm.

A SongDesc (tempo + list of ChannelDesc) packs to a self-contained blob:

    SongHeader:
      db  tempo
      db  channel_count
      ; per channel:
      db  route ; dw stream_ptr      (xchannel_count)
      dw  patch_table_ptr
    <stream 0 bytes><stream 1 bytes>...

Stream pointers are 16-bit BIG-ENDIAN offsets RELATIVE TO THE START OF THE BLOB
(the SongHeader label). The Task-6 loader adds the song's base address (the
Z80 $8000-window pointer) to turn them into absolute fetch pointers; emitting
relative offsets here keeps pack_song hermetic and testable without a linker.
patch_table_ptr is left 0 here (the packer doesn't own the FM patch table — the
song_table/loader wires it; the field exists so the layout is final).

emit_asm() writes the whole blob as `dc.b` (even-terminated, labeled) so the
build can include it and the test can round-trip the exact bytes.

Tests: python3 -m pytest tools/test_song_packer.py -q
"""

import os

# --- Opcode + route constants (mirror of sound_constants.asm) ---
MEV_REST = 0x80
MEV_NOTE_BASE = 0x81
MEV_NOTE_MAX = 0xDF          # pitch index 0..0x5E
MEV_VOL = 0xE0
MEV_PATCH = 0xE1
MEV_DAC = 0xE2
MEV_NOTE_DUR = 0xE3
MEV_LOOP_POINT = 0xEE
MEV_JUMP = 0xEF
MEV_END = 0xFF

MAX_PITCH = MEV_NOTE_MAX - MEV_NOTE_BASE   # = 0x5E
MAX_DUR = 0x7F                              # SetDur range $00..$7F

CHROUTE_FM1 = 0
CHROUTE_FM2 = 1
CHROUTE_FM3 = 2
CHROUTE_FM4 = 3
CHROUTE_FM5 = 4
CHROUTE_PSG1 = 5
CHROUTE_PSG2 = 6
CHROUTE_PSG3 = 7
CHROUTE_PSGN = 8
CHROUTE_DAC = 9
CHROUTE_COUNT = 10

_FM_ROUTES = {CHROUTE_FM1, CHROUTE_FM2, CHROUTE_FM3, CHROUTE_FM4, CHROUTE_FM5}


class PackError(Exception):
    pass


# --- Events ---------------------------------------------------------------

class Event:
    """Base event. `encode()` -> bytes; `validate(route)` raises PackError."""
    def encode(self) -> bytes:
        raise NotImplementedError

    def validate(self, route: int) -> None:
        pass


class SetDur(Event):
    def __init__(self, ticks: int):
        self.ticks = ticks

    def encode(self) -> bytes:
        return bytes([self.ticks & 0xFF])

    def validate(self, route):
        if not (0 <= self.ticks <= MAX_DUR):
            raise PackError(f"SetDur({self.ticks}) out of range 0..{MAX_DUR}")


class Rest(Event):
    def encode(self) -> bytes:
        return bytes([MEV_REST])


class Note(Event):
    def __init__(self, pitch: int):
        self.pitch = pitch

    def encode(self) -> bytes:
        return bytes([MEV_NOTE_BASE + self.pitch])

    def validate(self, route):
        if not (0 <= self.pitch <= MAX_PITCH):
            raise PackError(f"Note pitch {self.pitch} out of range 0..{MAX_PITCH}")


class Vol(Event):
    def __init__(self, vol: int):
        self.vol = vol

    def encode(self) -> bytes:
        return bytes([MEV_VOL, self.vol & 0xFF])

    def validate(self, route):
        if not (0 <= self.vol <= 127):
            raise PackError(f"Vol {self.vol} out of range 0..127")


class Patch(Event):
    def __init__(self, patch: int):
        self.patch = patch

    def encode(self) -> bytes:
        return bytes([MEV_PATCH, self.patch & 0xFF])

    def validate(self, route):
        if route not in _FM_ROUTES:
            raise PackError(f"Patch on non-FM route {route}")


class Dac(Event):
    def __init__(self, sample_id: int):
        self.sample_id = sample_id

    def encode(self) -> bytes:
        return bytes([MEV_DAC, self.sample_id & 0xFF])

    def validate(self, route):
        if route != CHROUTE_DAC:
            raise PackError(f"Dac on non-DAC route {route}")


class NoteDur(Event):
    def __init__(self, pitch: int, dur: int):
        self.pitch = pitch
        self.dur = dur

    def encode(self) -> bytes:
        return bytes([MEV_NOTE_DUR, self.pitch & 0xFF, self.dur & 0xFF])

    def validate(self, route):
        if not (0 <= self.pitch <= MAX_PITCH):
            raise PackError(f"NoteDur pitch {self.pitch} out of range")
        if not (0 <= self.dur <= 0xFF):
            raise PackError(f"NoteDur dur {self.dur} out of range")


class LoopPoint(Event):
    def encode(self) -> bytes:
        return bytes([MEV_LOOP_POINT])


class Jump(Event):
    def encode(self) -> bytes:
        return bytes([MEV_JUMP])


class End(Event):
    def encode(self) -> bytes:
        return bytes([MEV_END])


# --- Descriptors ----------------------------------------------------------

class ChannelDesc:
    def __init__(self, route: int, events: list):
        self.route = route
        self.events = events


class SongDesc:
    def __init__(self, tempo: int, channels: list):
        self.tempo = tempo
        self.channels = channels


# --- Packing --------------------------------------------------------------

def _validate_channel(ch: ChannelDesc) -> bytes:
    if not (0 <= ch.route < CHROUTE_COUNT):
        raise PackError(f"route {ch.route} out of range")
    saw_loop = False
    loop_advances_time = False    # any time-advancing event since the LoopPoint
    stream = bytearray()
    for ev in ch.events:
        ev.validate(ch.route)
        if isinstance(ev, LoopPoint):
            saw_loop = True
            loop_advances_time = False
        if saw_loop and isinstance(ev, (Note, Rest, NoteDur)):
            # Note ($81..$DF), Rest ($80), NoteDur ($E3) advance the tick clock;
            # all other events (SetDur, Vol, Patch, Dac, LoopPoint, Jump) are
            # zero-tick. A loop body with no time-advancing event would spin the
            # Z80 fetch loop forever (it never returns to the tick driver).
            loop_advances_time = True
        if isinstance(ev, Jump):
            if not saw_loop:
                raise PackError("Jump with no preceding LoopPoint")
            if not loop_advances_time:
                raise PackError(
                    "loop body has no time-advancing event "
                    "(Note/Rest/NoteDur) — would spin the sequencer forever")
        stream += ev.encode()
    if not ch.events:
        raise PackError("empty channel stream")
    last = ch.events[-1]
    if not isinstance(last, (Jump, End)):
        raise PackError("stream not terminated by Jump or End")
    return bytes(stream)


def pack_song(song: SongDesc) -> bytes:
    if not (0 <= song.tempo <= 0xFF):
        raise PackError(f"tempo {song.tempo} out of byte range")
    if not (1 <= len(song.channels) <= 0xFF):
        raise PackError("channel_count out of byte range")

    streams = [_validate_channel(ch) for ch in song.channels]

    n = len(song.channels)
    header_len = 2 + 3 * n + 2     # tempo, count, (route+dw)*n, dw patch_ptr

    # Stream offsets relative to blob start.
    offsets = []
    cur = header_len
    for s in streams:
        offsets.append(cur)
        cur += len(s)

    out = bytearray()
    out.append(song.tempo & 0xFF)
    out.append(n & 0xFF)
    for ch, off in zip(song.channels, offsets):
        out.append(ch.route & 0xFF)
        out.append((off >> 8) & 0xFF)   # big-endian
        out.append(off & 0xFF)
    out.append(0x00)                    # patch_table_ptr hi (wired by loader)
    out.append(0x00)                    # patch_table_ptr lo
    for s in streams:
        out += s
    return bytes(out)


def emit_asm(song: SongDesc, label: str) -> str:
    blob = pack_song(song)
    lines = []
    lines.append("; ======================================================================")
    lines.append("; %s.asm — GENERATED by tools/song_packer.py — DO NOT EDIT BY HAND." % label)
    lines.append("; Packed music song (Music format v0). Stream pointers in the header are")
    lines.append("; 16-bit BE offsets relative to the %s label (loader adds the base)." % label)
    lines.append("; ======================================================================")
    lines.append("")
    lines.append("%s:" % label)
    for i in range(0, len(blob), 16):
        chunk = blob[i:i + 16]
        lines.append("    dc.b   " + ", ".join("$%02X" % b for b in chunk))
    lines.append("%s_End:" % label)
    lines.append("")
    lines.append("    align 2")
    return "\n".join(lines)


def write_asm(song: SongDesc, label: str, out_path: str) -> None:
    with open(out_path, "w") as f:
        f.write(emit_asm(song, label))
        f.write("\n")
