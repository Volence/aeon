#!/usr/bin/env python3
"""song_packer — build-time music song description -> packed bytes + .asm.

A SongDesc (flags + tempo + tempo_base + list of ChannelDesc) packs to a
self-contained blob (Phase 3 C-ready header):

    SongHeader:
      db  flags            ; Sound 1D per-song playback mode (SH_F_* below)
      db  tempo            ; LEGACY Timer-A selector (Phase 3: unused)
      db  tempo_base       ; Phase 3 per-frame tempo accumulator base
      db  channel_count
      dw  pitchtable_ptr   ; per-song pitch table BE offset (0 = engine default)
      ; per channel:
      db  route ; dw cmd_ptr ; dw mod_ptr     (xchannel_count)
      dw  patch_table_ptr
    <stream 0 bytes><stream 1 bytes>...

Each channel descriptor commits a {cmd_ptr, mod_ptr} PAIR (the C-ready stream
seam): cmd_ptr = the command stream (slot[0], always present), mod_ptr = the
independent modulation stream (slot[1], 0/NULL for A / single-stream songs).
Reaching the full dual-stream end state is purely additive — no header change.

Stream pointers are 16-bit BIG-ENDIAN offsets RELATIVE TO THE START OF THE BLOB
(the SongHeader label). The loader adds the song's base address (the Z80
$8000-window pointer) to turn them into absolute fetch pointers; emitting
relative offsets here keeps pack_song hermetic and testable without a linker.
pitchtable_ptr and patch_table_ptr are left 0 here (the packer doesn't own the
pitch table or FM patch table — the song_table/loader wires them; the fields
exist so the layout is final).

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
MEV_PAN = 0xE4               # + b4: set channel pan/AMS/FMS (raw YM $B4 byte)
MEV_OPBIAS = 0xE9            # + op(0..3) + val(signed -128..127): per-op additive TL bias (neg=brighten)
MEV_REGDELTA = 0xEA          # + count + count*(reg_sel, value): mid-note minimal
                             # register deltas (voice-stepping). reg_sel =
                             # (group_code<<2)|op; see RegDelta below.
MEV_NOTE_RAW = 0xE7          # + a4 a0 dd: key a raw-frequency FM note (exact
                             # $A4/$A0) for duration dd, bypassing the pitch table
MEV_PITCHENV = 0xE8          # + count + count idx bytes: pitch-envelope note +
                             # key-on (each idx = absolute 0..$83 into the per-song
                             # fnum table). count==1 = plain note; >=2 = trill/arp.
# Bounded-repeat opcodes (Sound 1D Task 1). The sequencer interprets these in a
# later engine task; for now the packer ENCODES them so a song can wrap a body
# in a finite repeat instead of unrolling it (Moving Trucks would be ~100KB
# unrolled vs ~8KB with repeats).
MEV_REPEAT_START = 0xE5      # no operand: marks the start of a repeatable body
MEV_REPEAT_END = 0xE6        # + nn: replay from the matching REPEAT_START nn times
MEV_LOOP_POINT = 0xEE
MEV_JUMP = 0xEF
MEV_NOTEFILL = 0xED          # + master: per-channel note-fill (frames keyed from attack; 0=legato)
MEV_PSGENV = 0xEB           # + env_id: set the channel's PSG volume-envelope id (1-based; 0=none)
MEV_MODSET = 0xEC           # + wait speed change step: latch pitch-modulation params (all 0 = off)
MEV_SPINREV = 0xF0          # (no operand): add the global spindash rev into sc_transpose, cap $10
MEV_SPINREV_RESET = 0xF1    # (no operand): zero the global spindash rev
MEV_END = 0xFF

MAX_PITCH = MEV_NOTE_MAX - MEV_NOTE_BASE   # = 0x5E
MAX_DUR = 0x7F                              # SetDur range $00..$7F

# Channel-route enum — MIRROR of sound_constants.asm (Sound 1D inserts FM6 = 5
# and shifts PSG/DAC up by one). Keep in lockstep with the .asm or the packed
# route bytes will index the wrong writer on the Z80.
CHROUTE_FM1 = 0
CHROUTE_FM2 = 1
CHROUTE_FM3 = 2
CHROUTE_FM4 = 3
CHROUTE_FM5 = 4
CHROUTE_FM6 = 5      # Sound 1D: 6th FM voice (adaptive FM6 slot)
CHROUTE_PSG1 = 6
CHROUTE_PSG2 = 7
CHROUTE_PSG3 = 8
CHROUTE_PSGN = 9
CHROUTE_DAC = 10
CHROUTE_COUNT = 11

_FM_ROUTES = {CHROUTE_FM1, CHROUTE_FM2, CHROUTE_FM3, CHROUTE_FM4, CHROUTE_FM5,
              CHROUTE_FM6}
_PSG_ROUTES = {CHROUTE_PSG1, CHROUTE_PSG2, CHROUTE_PSG3, CHROUTE_PSGN}

# SongHeader flags byte (SH_FLAGS) — MIRROR of sound_constants.asm SH_F_*.
SH_F_FM6_FM = 1 << 0     # FM6 is a 6th FM sequencer voice (DAC mode OFF)
SH_F_STREAM = 1 << 1     # stream from ROM (no RAM copy); else copy-to-RAM (1C)
SH_F_FM6_ADAPTIVE = 1 << 2  # Layer 7: FM6 time-shares ch6 with the DAC (music between drum hits); requires SH_F_FM6_FM


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


class NoteFill(Event):
    """Gate articulation (#4): set the channel's note-fill master — the number of
    frames a note stays keyed from its attack before an early key-off (a staccato gap
    until the next attack). 0 = legato/off. Per-channel, persists until changed.
    Zero-tick; the per-frame countdown + key-off run in the engine (ModUpdate)."""
    def __init__(self, master: int):
        self.master = master

    def encode(self) -> bytes:
        return bytes([MEV_NOTEFILL, self.master & 0xFF])

    def validate(self, route):
        if not (0 <= self.master <= 255):
            raise PackError(f"NoteFill {self.master} out of range 0..255")
        if route not in _FM_ROUTES:
            raise PackError(f"NoteFill on non-FM route {route}")


class Patch(Event):
    def __init__(self, patch: int):
        self.patch = patch

    def encode(self) -> bytes:
        return bytes([MEV_PATCH, self.patch & 0xFF])

    def validate(self, route):
        if route not in _FM_ROUTES:
            raise PackError(f"Patch on non-FM route {route}")


class Pan(Event):
    """Phase-3 pan: set the channel's pan/AMS/FMS (the raw YM $B4 byte). The
    YM2612 $B4 layout is bit7 = LEFT-output enable, bit6 = RIGHT-output enable,
    bits5-4 = AMS, bits2-0 = FMS. So hard-LEFT = $80, hard-RIGHT = $40, both
    (center) = $C0, silent = $00 (with AMS/FMS = 0). Zero-tick coordination
    setter; rendered to $B4+chan by ModUpdate write-on-change. FM-only effect.
    This packer IS the transcoder, so it emits the hardware-correct $B4 byte."""
    PAN_OFF = 0x00
    PAN_LEFT = 0x80     # bit7 = Left output enable
    PAN_RIGHT = 0x40    # bit6 = Right output enable
    PAN_CENTER = 0xC0   # both

    def __init__(self, b4: int):
        self.b4 = b4

    def encode(self) -> bytes:
        return bytes([MEV_PAN, self.b4 & 0xFF])

    def validate(self, route):
        if not (0 <= self.b4 <= 0xFF):
            raise PackError(f"Pan b4 {self.b4} out of byte range")


class PsgEnv(Event):
    """SFX-fidelity PSG volume envelope: set the channel's 1-based env id (0=none).
    The engine restarts the contour cursor on each attack and folds the per-frame
    attenuation delta into Psg_SetVolume (S3K VolEnv contour). PSG/noise routes only.
    Zero-tick coordination setter; the body bytes live in the engine's PsgVolEnv_Table
    (keyed by id == sTone number). Mirrors the OpBias/Pan emit pattern."""
    def __init__(self, env_id: int):
        self.env_id = env_id

    def encode(self) -> bytes:
        return bytes([MEV_PSGENV, self.env_id & 0xFF])

    def validate(self, route):
        if route in _FM_ROUTES:
            raise PackError(f"PsgEnv on FM route {route}")
        if not (0 <= self.env_id <= 0xFF):
            raise PackError(f"PsgEnv env_id {self.env_id} out of byte range")


class ModSet(Event):
    """SFX-fidelity pitch modulation (the engine's smpsModSet): latch wait/speed/
    change/step. The engine re-arms per FM note (accum=0, the step count seeded
    raw>>1 per S3K's srl, then each reversal reloads the FULL raw step) and renders a
    continuous additive freq-word vibrato/sweep with NO re-key. All-zero = mod off
    (the smpsModSet 0,0,0,0 idiom AB/3C use to cancel modulation). `change` (the
    per-step delta) is a SIGNED byte (-128..127); wait/speed/step are unsigned. FM
    here (Task 4); PSG modulation reuses the same opcode/state (Task 5)."""
    def __init__(self, wait: int, speed: int, change: int, step: int):
        self.wait = wait
        self.speed = speed
        self.change = change
        self.step = step

    def encode(self) -> bytes:
        return bytes([MEV_MODSET, self.wait & 0xFF, self.speed & 0xFF,
                      self.change & 0xFF, self.step & 0xFF])

    def validate(self, route):
        for name, v in (('wait', self.wait), ('speed', self.speed), ('step', self.step)):
            if not (0 <= v <= 0xFF):
                raise PackError(f"ModSet {name} {v} out of byte range 0..255")
        if not (-128 <= self.change <= 127):
            raise PackError(f"ModSet change {self.change} out of signed byte range -128..127")


class SpinRev(Event):
    """SFX-fidelity spindash rev (the engine's smpsSpindashRev): add the global rev
    into this channel's transpose, cap $10, increment the global. Runtime-escalating
    by re-trigger count (the engine keeps the global byte). Zero-tick, no operand."""
    def encode(self) -> bytes:
        return bytes([MEV_SPINREV])


# NOTE: there is deliberately NO SpinRevReset event. The spindash rev reset is
# DISPATCH-FOLDED in the engine (Sfx_BeginSound zeroes Snd_SpindashRev for any
# non-spindash id), so $F1/MEV_SPINREV_RESET must NEVER appear in a stream — the
# engine maps $F1 to Seq_BadOpcode. smpsResetSpindashRev transcodes to nothing.


class OpBias(Event):
    """Phase-3 per-operator TL bias: add SIGNED `val` to operator `op`'s patch TL
    (the $40-group). op = 0..3 (physical reg offset +0/+4/+8/+C = S1,S3,S2,S4).
    `val` is signed -128..127: NEGATIVE brightens (reduces attenuation), POSITIVE
    darkens. The engine clamps the sum to [0,$7F] (TL is 7-bit attenuation: $00 =
    loudest, $7F = silent). Encoded as a two's-complement byte. Latched at the
    next patch load / note (the Zyrinx key-on latch), so route an OpBias before a
    Patch to apply it. Zero-tick. FM-only."""
    def __init__(self, op: int, val: int):
        self.op = op
        self.val = val

    def encode(self) -> bytes:
        return bytes([MEV_OPBIAS, self.op & 0xFF, self.val & 0xFF])

    def validate(self, route):
        if route not in _FM_ROUTES:
            raise PackError(f"OpBias on non-FM route {route}")
        if not (0 <= self.op <= 3):
            raise PackError(f"OpBias op {self.op} out of range 0..3")
        if not (-128 <= self.val <= 127):
            raise PackError(f"OpBias val {self.val} out of signed byte range -128..127")


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


class NoteRaw(Event):
    """Key an FM note at a RAW frequency word (the exact $A4/$A0 bytes) for an
    explicit duration, bypassing the pitch table. Used by VGM-derived songs to
    reproduce the original chip pitch exactly. Time-advancing. FM-only."""
    def __init__(self, a4: int, a0: int, dur: int):
        self.a4 = a4        # $A4 value = (block<<3)|fnumHi
        self.a0 = a0        # $A0 value = fnum low byte
        self.dur = dur

    def encode(self) -> bytes:
        return bytes([MEV_NOTE_RAW, self.a4 & 0xFF, self.a0 & 0xFF,
                      self.dur & 0xFF])

    def validate(self, route):
        if route not in _FM_ROUTES:
            raise PackError(f"NoteRaw on non-FM route {route}")
        if not (0 <= self.a4 <= 0xFF and 0 <= self.a0 <= 0xFF):
            raise PackError(f"NoteRaw fnum bytes out of range")
        if not (1 <= self.dur <= 0xFF):
            raise PackError(f"NoteRaw dur {self.dur} out of range 1..255")


PITCHENV_MAX_IDX = 0x83      # absolute fnum-table index ceiling (132-entry table)


class PitchEnv(Event):
    """Phase-3 pitch-envelope note (Zyrinx-style). Sets 1..5 pitch points (each
    an ABSOLUTE index 0..$83 into the per-song fnum table) and arms a (re)key;
    the Z80 renders it via ModUpdate. count==1 = a plain note; count>=2 = a
    trill/arp (cursor-cycled on the chip). Time-advancing (paced like a bare
    Note by the channel's default duration / a following WAIT). FM-only."""
    def __init__(self, points):
        if isinstance(points, int):
            points = [points]
        self.points = list(points)

    def encode(self) -> bytes:
        return bytes([MEV_PITCHENV, len(self.points) & 0xFF]
                     + [p & 0xFF for p in self.points])

    def validate(self, route):
        if route not in _FM_ROUTES:
            raise PackError(f"PitchEnv on non-FM route {route}")
        if not (1 <= len(self.points) <= 5):
            raise PackError(
                f"PitchEnv point count {len(self.points)} out of range 1..5")
        for p in self.points:
            if not (0 <= p <= PITCHENV_MAX_IDX):
                raise PackError(
                    f"PitchEnv point {p} out of range 0..{PITCHENV_MAX_IDX}")


# --- reg_sel encoding (mirror of sound_constants.asm) ---------------------
# reg_sel = (group_code << REGDELTA_GROUP_SHIFT) | op:
#   op (bits 1-0)         = physical operator 0..3 (reg offset +0/+4/+8/+C = S1,S3,S2,S4)
#   group_code (bits 5-2) = index into the per-operator register-group bases:
#       0=$30 DT/MUL, 1=$40 TL, 2=$50 RS/AR, 3=$60 AM/D1R, 4=$70 D2R, 5=$80 D1L/RR.
REGDELTA_OP_MASK = 0x03
REGDELTA_GROUP_SHIFT = 2
REGDELTA_GROUP_COUNT = 6
# group_code constants for callers (the TL group op0 = the canonical lead voice-step).
RD_GROUP_DT_MUL = 0   # $30
RD_GROUP_TL = 1       # $40 (TL — the rapid lead voice-step)
RD_GROUP_RS_AR = 2    # $50
RD_GROUP_AM_D1R = 3   # $60
RD_GROUP_D2R = 4      # $70
RD_GROUP_D1L_RR = 5   # $80


def reg_sel(group_code: int, op: int) -> int:
    """Encode a reg_sel byte = (group_code << 2) | op (see the constants above)."""
    if not (0 <= op <= 3):
        raise PackError(f"reg_sel op {op} out of range 0..3")
    if not (0 <= group_code < REGDELTA_GROUP_COUNT):
        raise PackError(
            f"reg_sel group_code {group_code} out of range 0..{REGDELTA_GROUP_COUNT-1}")
    return (group_code << REGDELTA_GROUP_SHIFT) | op


class RegDelta(Event):
    """Phase-3 voice-stepping: write `count` per-operator YM2612 registers
    IMMEDIATELY (mid-note) for the channel, part-aware. Each entry is a
    (reg_sel, value) pair where reg_sel = (group_code<<2)|op encodes the
    per-operator register group + operator (use reg_sel()/the RD_GROUP_* consts).

    This is the MINIMAL-DELTA voice-step: a held note's timbre is swept by writing
    only the registers that change between voice steps. The Zyrinx rapid lead step
    differs by ONE byte (operator S1's TL = the $40 group op0), so a rapid step is
    one RegDelta with a single (reg_sel(RD_GROUP_TL, 0), tl) pair.

    Does NOT re-key (no $28 write, no SCF_REKEY): per the re-key rule only a pitch
    change (PitchEnv) re-articulates. Zero-tick coordination setter; FM-only.

    `entries` is a list of (reg_sel, value) tuples, or pass the convenience
    RegDelta.tl(op, tl) classmethod for the common single-TL sweep step."""

    def __init__(self, entries):
        # accept a single (reg_sel, value) tuple too.
        if entries and isinstance(entries[0], int):
            entries = [tuple(entries)]
        self.entries = [tuple(e) for e in entries]

    @classmethod
    def tl(cls, op: int, tl: int):
        """Convenience: one operator-TL write (the canonical voice-step)."""
        return cls([(reg_sel(RD_GROUP_TL, op), tl)])

    def encode(self) -> bytes:
        out = [MEV_REGDELTA, len(self.entries) & 0xFF]
        for rs, val in self.entries:
            out.append(rs & 0xFF)
            out.append(val & 0xFF)
        return bytes(out)

    def validate(self, route):
        if route not in _FM_ROUTES:
            raise PackError(f"RegDelta on non-FM route {route}")
        if not (1 <= len(self.entries) <= 255):
            raise PackError(
                f"RegDelta count {len(self.entries)} out of range 1..255")
        for rs, val in self.entries:
            if not (0 <= rs <= 0xFF):
                raise PackError(f"RegDelta reg_sel {rs} out of byte range")
            group = (rs >> REGDELTA_GROUP_SHIFT) & 0x0F
            if group >= REGDELTA_GROUP_COUNT:
                raise PackError(
                    f"RegDelta reg_sel {rs:#04x} group_code {group} >= "
                    f"{REGDELTA_GROUP_COUNT} (no such register group)")
            if not (0 <= val <= 0xFF):
                raise PackError(f"RegDelta value {val} out of byte range")


class RepeatStart(Event):
    """Marks the start of a body that MEV_REPEAT_END replays. No operand."""
    def encode(self) -> bytes:
        return bytes([MEV_REPEAT_START])


class RepeatEnd(Event):
    """Replays from the matching RepeatStart `count` total times (1..255).
    count == 1 plays the body once (no repeat)."""
    def __init__(self, count: int):
        self.count = count

    def encode(self) -> bytes:
        return bytes([MEV_REPEAT_END, self.count & 0xFF])

    def validate(self, route):
        if not (1 <= self.count <= 255):
            raise PackError(
                f"RepeatEnd count {self.count} out of range 1..255")


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
    def __init__(self, tempo: int, channels: list, flags: int = 0,
                 tempo_base: int = None, pitchtable=None):
        self.tempo = tempo
        self.channels = channels
        self.flags = flags          # SH_FLAGS byte (SH_F_* OR'd); 0 = 1C copy/DAC
        # Optional per-song pitch table the song carries in its own bank (a
        # streaming song with a custom fnum table). The packer does NOT read this
        # field — pack_song takes the resolved BE pitchtable_offset as a separate
        # argument — so it is metadata that a caller (e.g. convert_song) attaches
        # for the song_table/loader to wire up. None = use the engine default
        # pitch table (the SongHeader pitchtable_ptr stays 0).
        self.pitchtable = pitchtable
        # Phase 3: per-frame tempo accumulator base. The per-frame engine does a
        # single `sub 16` per frame, so it can yield at most one event-tick per
        # frame and REQUIRES tempo_base >= 16 (a value 1..15 packs but plays at a
        # wildly wrong rate). Songs should set this explicitly via the
        # frame-rate event-rate math. When omitted we fall back to the legacy
        # `tempo` (Timer-A selector) but CLAMP it up to the 16 floor so the
        # default can never produce a silent mis-tempo — a too-low legacy tempo
        # plays at the slowest valid rate instead of breaking. pack_song still
        # hard-validates the final value, so an explicit out-of-range value
        # raises rather than being silently clamped.
        self.tempo_base = max(16, tempo) if tempo_base is None else tempo_base


# --- Packing --------------------------------------------------------------

def _validate_channel(ch: ChannelDesc) -> bytes:
    if not (0 <= ch.route < CHROUTE_COUNT):
        raise PackError(f"route {ch.route} out of range")
    saw_loop = False
    loop_advances_time = False    # any time-advancing event since the LoopPoint
    saw_first_note = False        # first time-advancing event seen yet?
    saw_patch = False             # Patch ($E1) seen in the setup run?
    saw_vol = False               # Vol ($E0) seen in the setup run?
    repeat_depth = 0              # open RepeatStart count (nesting)
    repeat_time_stack = []        # per open RepeatStart: saw a time-advancing event
    stream = bytearray()
    for ev in ch.events:
        ev.validate(ch.route)
        if isinstance(ev, RepeatStart):
            repeat_depth += 1
            repeat_time_stack.append(False)
        if isinstance(ev, RepeatEnd):
            if repeat_depth <= 0:
                raise PackError("RepeatEnd with no preceding RepeatStart")
            repeat_depth -= 1
            if not repeat_time_stack.pop():
                raise PackError(
                    "RepeatStart..RepeatEnd body has no time-advancing event "
                    "(Note/Rest/NoteDur) — the Z80 would replay it in a single "
                    "frame (loop collapse)")
        if isinstance(ev, (Note, Rest, NoteDur, NoteRaw, PitchEnv)) and repeat_time_stack:
            repeat_time_stack = [True] * len(repeat_time_stack)
        if isinstance(ev, Patch):
            saw_patch = True
        if isinstance(ev, Vol):
            saw_vol = True
        if isinstance(ev, (Note, Rest, NoteDur, NoteRaw, PitchEnv)) and not saw_first_note:
            # First time-advancing event of the channel: this is the first point
            # the chip is keyed. Each route class must be initialized first or it
            # plays the YM2612/SN76489 power-on garbage register state. The DAC
            # route only triggers samples ($E2), so it is exempt.
            #   FM  routes: need BOTH Patch ($E1) AND Vol ($E0) first.
            #   PSG routes: need Vol ($E0) first (PSG has no patch — $E1 is
            #               already rejected on non-FM routes).
            saw_first_note = True
            if ch.route in _FM_ROUTES:
                if not saw_patch:
                    raise PackError(
                        "FM channel keys a note before a Patch ($E1) — would "
                        "play the YM2612 power-on garbage voice")
                if not saw_vol:
                    raise PackError(
                        "FM channel keys a note before a Vol ($E0) — would "
                        "play at undefined volume")
            elif ch.route in _PSG_ROUTES:
                if not saw_vol:
                    raise PackError(
                        "PSG channel keys a note before a Vol ($E0) — would "
                        "play at undefined attenuation")
        if isinstance(ev, LoopPoint):
            saw_loop = True
            loop_advances_time = False
        if saw_loop and isinstance(ev, (Note, Rest, NoteDur, NoteRaw, PitchEnv)):
            # Note ($81..$DF), Rest ($80), NoteDur ($E3), NoteRaw ($E7), and
            # PitchEnv ($E8) advance the tick clock; all other events (SetDur, Vol,
            # Patch, Dac, LoopPoint, Jump) are zero-tick. A loop body with no
            # time-advancing event would spin the Z80 fetch loop forever (it never
            # returns to the tick driver).
            loop_advances_time = True
        if isinstance(ev, Jump):
            if not saw_loop:
                raise PackError("Jump with no preceding LoopPoint")
            if not loop_advances_time:
                raise PackError(
                    "loop body has no time-advancing event "
                    "(Note/Rest/NoteDur) — would spin the sequencer forever")
        stream += ev.encode()
    if repeat_depth != 0:
        raise PackError(
            f"{repeat_depth} RepeatStart(s) not closed by a RepeatEnd")
    if not ch.events:
        raise PackError("empty channel stream")
    last = ch.events[-1]
    if not isinstance(last, (Jump, End)):
        raise PackError("stream not terminated by Jump or End")
    return bytes(stream)


def pack_song(song: SongDesc, pitchtable_offset: int = 0) -> bytes:
    """Pack a SongDesc to bytes. pitchtable_offset (default 0 = engine default)
    is the SongHeader pitchtable_ptr field — a 16-bit BE offset, relative to the
    song header, of the per-song pitch table (for a streaming song that carries
    its own table in the same bank). The loader resolves it to base+offset; 0
    leaves the engine-default table in use. The copy-path scratch songs leave it
    0 (their pitch table is the inline engine default)."""
    if not (0 <= song.tempo <= 0xFF):
        raise PackError(f"tempo {song.tempo} out of byte range")
    if not (16 <= song.tempo_base <= 0xFF):
        raise PackError(
            f"tempo_base {song.tempo_base} out of range 16..255 (the per-frame "
            f"tempo accumulator caps at one event-tick/frame; tempo_base<16 "
            f"mis-plays)")
    if not (0 <= song.flags <= 0xFF):
        raise PackError(f"flags {song.flags} out of byte range")
    # Layer 7: adaptive FM6 time-share REQUIRES FM6 to be an FM voice (SH_F_FM6_FM) and
    # the stream load path (SH_F_STREAM sets $2B=$00 = FM6 plays music at load). Without
    # FM6_FM the trigger/exhaust would toggle $2B on a song that never plays FM6 music;
    # without STREAM the copy path leaves $2B=$80 (DAC) and the exhaust's $2B=$00 would
    # mis-handle it. Catch the malformed combo at pack time, not on hardware.
    if (song.flags & SH_F_FM6_ADAPTIVE) and not (song.flags & SH_F_FM6_FM):
        raise PackError("SH_F_FM6_ADAPTIVE requires SH_F_FM6_FM (FM6 must be an FM voice to time-share with the DAC)")
    if (song.flags & SH_F_FM6_ADAPTIVE) and not (song.flags & SH_F_STREAM):
        raise PackError("SH_F_FM6_ADAPTIVE requires SH_F_STREAM (the stream load path sets $2B=$00 so FM6 plays music at load)")
    if not (1 <= len(song.channels) <= 0xFF):
        raise PackError("channel_count out of byte range")
    if not (0 <= pitchtable_offset <= 0xFFFF):
        raise PackError(
            f"pitchtable_offset {pitchtable_offset} out of 16-bit range")

    streams = [_validate_channel(ch) for ch in song.channels]

    n = len(song.channels)
    # Phase 3 C-ready header:
    #   flags, tempo, tempo_base, count, dw pitchtable_ptr,
    #   (route + dw cmd_ptr + dw mod_ptr)*n, dw patch_table_ptr.
    header_len = 4 + 2 + 5 * n + 2

    # Stream offsets relative to blob start.
    offsets = []
    cur = header_len
    for s in streams:
        offsets.append(cur)
        cur += len(s)

    out = bytearray()
    out.append(song.flags & 0xFF)
    out.append(song.tempo & 0xFF)
    out.append(song.tempo_base & 0xFF)
    out.append(n & 0xFF)
    out.append((pitchtable_offset >> 8) & 0xFF)   # pitchtable_ptr hi (BE)
    out.append(pitchtable_offset & 0xFF)          # pitchtable_ptr lo (0 = default)
    for ch, off in zip(song.channels, offsets):
        out.append(ch.route & 0xFF)
        out.append((off >> 8) & 0xFF)   # cmd_ptr big-endian
        out.append(off & 0xFF)
        out.append(0x00)                # mod_ptr = 0 / NULL (single-stream A)
        out.append(0x00)
    out.append(0x00)                    # patch_table_ptr hi (wired by loader)
    out.append(0x00)                    # patch_table_ptr lo
    for s in streams:
        out += s
    return bytes(out)


def emit_asm(song: SongDesc, label: str, pitchtable_offset: int = 0) -> str:
    blob = pack_song(song, pitchtable_offset=pitchtable_offset)
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


def write_asm(song: SongDesc, label: str, out_path: str,
              pitchtable_offset: int = 0) -> None:
    with open(out_path, "w") as f:
        f.write(emit_asm(song, label, pitchtable_offset=pitchtable_offset))
        f.write("\n")
