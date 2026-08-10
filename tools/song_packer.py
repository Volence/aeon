#!/usr/bin/env python3
"""song_packer — build-time music song description -> packed bytes + .asm.

A SongDesc (flags + tempo + tempo_mod + list of ChannelDesc) packs to a
self-contained blob (Phase 3 C-ready header):

    SongHeader:
      db  flags            ; Sound 1D per-song playback mode (SH_F_* below)
      db  tempo            ; LEGACY Timer-A selector (Phase 3: unused)
      db  tempo_mod        ; Phase 3 tempo mod (raw S3K TempoWait addend; SMPS
                           ; pass-through: 0 = full speed, rate = (256-mod)/256)
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
MEV_PSGNOISE = 0xF2         # + ctrl: set the SN76489 noise control byte ($E0-$EF, mode+rate)
MEV_END = 0xFF
# Phase-3 macro/automation-spine opcodes (mirror of sound_constants.asm;
# added by Components A/B/D on the asm side). Music-legal (see _validate_channel).
MEV_FMENV = 0xF7            # + env_id: arm the FM carrier-TL volume envelope (1-based; 0=off)
MEV_REGWRITE = 0xF8         # + part(0/1) + reg + val: inline raw YM2612 register write
MEV_MACRO = 0xF9            # + ptr_hi + ptr_lo: (re)arm the slot[1] macro stream at a blob offset
# Phase-2 per-note + global expression opcodes (mirror of sound_constants.asm).
MEV_TEMPO = 0xF3           # + dd: set the GLOBAL tempo mod (raw S3K TempoWait addend; 0 = full speed)
MEV_LFO = 0xF4             # + value: write YM2612 $22 (bit3 enable | bits0-2 rate); DAC $2A re-parked
MEV_PORTA = 0xF5           # + dd: set the persistent portamento glide rate (fnum/divisor units
                           # per frame; 0 = off -> notes snap)
MEV_DETUNE = 0xF6          # + dd (signed): set the channel's fine-pitch detune (applied at note-on)
MEV_EXT = 0xFA             # extension prefix ($FA + sub-opcode = 256 more event
                           # kinds, zero format break). Sub-op 0 = COMM (the Comm
                           # event: score-authored cue byte -> SND_STAT_COMM);
                           # sub-ops 1-255 remain free. An unknown sub-op is a
                           # pack error AND an engine trap (Seq_BadOpcode) — a
                           # new sub-op requires a driver update by construction,
                           # because payload lengths are unknown to a skipper.
MEV_EXT_COMM = 0x00        # MEV_EXT sub-op 0: + value -> SND_STAT_COMM

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

# --- D8 music-legal opcode gate ---------------------------------------
# song_packer IS the music-song builder, so every opcode it can emit is
# music-legal BY CONSTRUCTION except the dispatch-folded ones that must never
# appear in a stream (the engine maps them to Seq_BadOpcode). $F1
# (MEV_SPINREV_RESET) is reset-by-dispatch (Sfx_BeginSound zeroes the rev), so
# a raw event encoding it is music-ILLEGAL — reject, never silently emit. The
# Phase-3 expression opcodes ($F7/$F8/$F9) + MEV_PSGENV ($EB) are explicitly
# music-LEGAL (this set documents that intent for D8 traceability).
# MEV_SPINREV_RESET is defined above (~line 69) — referenced here, NOT redefined.
_MUSIC_ILLEGAL_OPCODES = frozenset({MEV_SPINREV_RESET})
_MUSIC_LEGAL_EXPRESSION_OPCODES = frozenset({
    MEV_PSGENV, MEV_FMENV, MEV_REGWRITE, MEV_MACRO, MEV_DETUNE, MEV_LFO, MEV_TEMPO,
    MEV_PORTA, MEV_EXT})

# SongHeader flags byte (SH_FLAGS) — MIRROR of sound_constants.asm SH_F_*.
SH_F_FM6_FM = 1 << 0     # FM6 is a 6th FM sequencer voice (DAC mode OFF)
SH_F_STREAM = 1 << 1     # stream from ROM — the ONLY load mode (the engine's COPY
                         # path was deleted, budget A.1). The bit stays reserved in
                         # the header contract; pack_song FORCE-SETS it on every
                         # packed song (the packer is the format authority).
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


class FmEnv(Event):
    """Phase-3 FM carrier-TL volume envelope: arm the channel's 1-based env id
    (0=off). Mirrors PsgEnv but routes to the FM-TL renderer (FmEnvUpdate); the
    engine resets the contour cursor on each attack and folds sc_env_out into the
    carrier-TL delta in Fm_SetVolume. FM routes only. Zero-tick. The shared
    MEV_FMENV dispatch entry points at the same Seq_Op_PsgEnv handler (it sets
    sc_env + cursor regardless of route); the RENDERER picks FM vs PSG by route."""
    def __init__(self, env_id: int):
        self.env_id = env_id

    def encode(self) -> bytes:
        return bytes([MEV_FMENV, self.env_id & 0xFF])

    def validate(self, route):
        if route not in _FM_ROUTES:
            raise PackError(f"FmEnv on non-FM route {route}")
        if not (0 <= self.env_id <= 0xFF):
            raise PackError(f"FmEnv env_id {self.env_id} out of byte range")


class RegWrite(Event):
    """Phase-3 inline raw YM2612 register write (slot[0]). Operands in stream
    order: part (0/1 — the explicit YM part, NOT derived from the channel), reg,
    val. The engine writes reg->addr port + val->data port for that part, then
    re-parks $2A. REFUSES reg $2A/$2B (DAC data/enable: an authored poke
    corrupts/silences the DAC stream) AND the $24-$27 timer block (Timer A is
    the whole-driver frame clock; the engine skips such writes, so the packer
    rejects them up front). Zero-tick. FM routes, plus the narrow DAC-route
    door (part 1 reg $B6 = DAC pan)."""
    def __init__(self, part: int, reg: int, val: int):
        self.part = part
        self.reg = reg
        self.val = val

    def encode(self) -> bytes:
        return bytes([MEV_REGWRITE, self.part & 0xFF, self.reg & 0xFF,
                      self.val & 0xFF])

    def validate(self, route):
        if route == CHROUTE_DAC:
            # Narrow DAC-route door: FM6's $B6 (part 1) is the DAC output's
            # pan register — S3K DAC tracks author L/C/R pan this way (HCZ2
            # tom fills). The Z80 handler is route-agnostic (explicit part),
            # so only this packer gate stood in the way. Any other register
            # from a DAC stream stays refused.
            if (self.part, self.reg) != (1, 0xB6):
                raise PackError(
                    f"RegWrite on the DAC route is limited to part 1 reg $B6 "
                    f"(FM6 pan); got part {self.part} reg {self.reg:#x}")
        elif route not in _FM_ROUTES:
            raise PackError(f"RegWrite on non-FM route {route}")
        if self.part not in (0, 1):
            raise PackError(f"RegWrite part {self.part} must be 0 or 1")
        if self.reg in (0x2A, 0x2B):
            raise PackError(
                f"RegWrite reg {self.reg:#x} is a DAC register ($2A/$2B) — "
                f"refused (would corrupt the DAC stream)")
        if 0x24 <= self.reg <= 0x27:
            raise PackError(
                f"RegWrite reg {self.reg:#x} is in the YM timer block ($24-$27) — "
                f"refused (Timer A is the whole-driver frame clock; the engine "
                f"skips these writes)")
        if not (0 <= self.reg <= 0xFF):
            raise PackError(f"RegWrite reg {self.reg} out of byte range")
        if not (0 <= self.val <= 0xFF):
            raise PackError(f"RegWrite val {self.val} out of byte range")


class Macro(Event):
    """Phase-3 (re)arm the slot[1] macro/automation stream (MacroTick) from
    slot[0]. Encodes a 2-byte BIG-ENDIAN blob-offset operand pointing at this
    channel's macro body; the offset is resolved (back-patched) by pack_song
    once body layout is known. The Z80 handler rebases it (base+offset, same
    convention as the loader's mod_ptr) into sc_mod_ptr + marks the stream
    active + resets. The bare event carries a placeholder 0 until packed."""
    def __init__(self):
        self.body_offset = 0     # back-patched by pack_song

    def encode(self) -> bytes:
        return bytes([MEV_MACRO, (self.body_offset >> 8) & 0xFF,
                      self.body_offset & 0xFF])

    def validate(self, route):
        if route not in _FM_ROUTES:
            raise PackError(f"Macro on non-FM route {route}")


# --- slot[1] macro-stream PRIVATE tag namespace (mirror of sound_constants.asm
# TAG_MAC_*; the D-side MacroTick reader consumes these EXACT bytes). These are
# NOT slot[0] MEV opcodes and NOT YM register values — a distinct namespace. ---
TAG_MAC_NEXT = 0xE0     # yield: advance exactly one frame
TAG_MAC_REG = 0xE1      # + part(0/1) + reg + val: immediate YM write + repark ($2A/$2B guarded)
TAG_MAC_LOOP = 0xE2     # + body_base_hi + body_base_lo (BE): cursor = body start (reader adds Snd_SongBase)
TAG_MAC_END = 0xE3      # disable the stream (mark inert)


class MacEvent:
    """Base slot[1] macro-stream event. encode(body_base) -> bytes."""
    def encode(self, body_base: int) -> bytes:
        raise NotImplementedError


class MacNext(MacEvent):
    """Yield: advance exactly one frame."""
    def encode(self, body_base: int) -> bytes:
        return bytes([TAG_MAC_NEXT])


class MacReg(MacEvent):
    """Immediate YM2612 register write in the macro stream: part(0/1), reg, val.
    Refuses reg $2A/$2B (DAC data/enable) and a control-code-valued data byte
    (a val that collides with a TAG_MAC_* byte would be safe here because tags
    are operand-position-decoded, but we reject it to match the spec's
    control-code-as-data guard and keep bodies inspectable)."""
    def __init__(self, part: int, reg: int, val: int):
        self.part = part
        self.reg = reg
        self.val = val

    def encode(self, body_base: int) -> bytes:
        if self.part not in (0, 1):
            raise PackError(f"MacReg part {self.part} must be 0 or 1")
        if self.reg in (0x2A, 0x2B):
            raise PackError(
                f"MacReg reg {self.reg:#x} is a DAC register ($2A/$2B) — refused")
        if 0x24 <= self.reg <= 0x27:
            raise PackError(
                f"MacReg reg {self.reg:#x} is in the YM timer block ($24-$27) — "
                f"refused (engine guards these; see MEV_REGWRITE)")
        if not (0 <= self.reg <= 0xFF):
            raise PackError(f"MacReg reg {self.reg} out of byte range")
        if not (0 <= self.val <= 0xFF):
            raise PackError(f"MacReg val {self.val} out of byte range")
        if TAG_MAC_NEXT <= self.val <= TAG_MAC_END:
            raise PackError(
                f"MacReg val {self.val:#x} collides with a TAG_MAC_* control "
                f"byte (${TAG_MAC_NEXT:02X}..${TAG_MAC_END:02X}) — reject "
                f"control-code-valued data")
        return bytes([TAG_MAC_REG, self.part & 0xFF, self.reg & 0xFF,
                      self.val & 0xFF])


class MacLoop(MacEvent):
    """Loop to the body start: emits TAG_MAC_LOOP + a 2-byte BIG-ENDIAN
    body_base offset (where this channel's macro body begins in the blob).
    The D-side reader adds Snd_SongBase to rebase it."""
    def encode(self, body_base: int) -> bytes:
        return bytes([TAG_MAC_LOOP, (body_base >> 8) & 0xFF, body_base & 0xFF])


class MacEnd(MacEvent):
    """Disable the stream (mark inert)."""
    def encode(self, body_base: int) -> bytes:
        return bytes([TAG_MAC_END])


def emit_macro_body(events, body_base: int) -> bytes:
    """Pack a slot[1] macro body (a list of MacEvent) to bytes. body_base is the
    blob offset where this body begins (known at body-layout time); it is the
    value a MacLoop encodes for its 2-byte BE loop target. Validates the
    $2A/$2B reg reject + control-code-as-data via each MacReg.encode().

    When the body terminates with MacLoop it MUST contain at least one MacNext
    before the MacLoop. MacroTick executes events until a TAG_MAC_NEXT yield;
    a loop body with no yield spins the Z80 forever (hard hang)."""
    if not events:
        raise PackError("empty macro body")
    if not isinstance(events[-1], (MacEnd, MacLoop)):
        raise PackError("macro body not terminated by MacEnd or MacLoop")
    for i, ev in enumerate(events[:-1]):
        # A terminator anywhere but the end makes everything after it
        # unreachable — and a MID-body MacLoop with no prior MacNext would
        # spin MacroTick forever (the terminal-only yield check below would
        # never see it). Reject non-terminal terminators outright.
        if isinstance(ev, (MacLoop, MacEnd)):
            raise PackError(
                "non-terminal %s at macro-body index %d — events after it are "
                "unreachable (MacLoop/MacEnd must be the body's LAST event)"
                % (type(ev).__name__, i))
    if isinstance(events[-1], MacLoop):
        # Every event before the terminal MacLoop is the body. Check that at
        # least one of them is a MacNext (TAG_MAC_NEXT yield). Without a yield
        # the Z80 MacroTick loop never returns to the tick driver — hard hang.
        if not any(isinstance(ev, MacNext) for ev in events[:-1]):
            raise PackError(
                "macro body loop has no TAG_MAC_NEXT yield — would hang Z80 "
                "(MacroTick spins until a MacNext/TAG_MAC_NEXT is reached)")
    out = bytearray()
    for ev in events:
        out += ev.encode(body_base)
    return bytes(out)


class PsgNoise(Event):
    """Set the SN76489 noise control byte (mode+rate, $E0-$EF). Zero-tick; owns the
    noise mode so a noise NOTE then carries PITCH for the rate-3 tone-2 clock. Emitted
    from the song's smpsPSGform. Noise route only."""
    def __init__(self, ctrl: int):
        self.ctrl = ctrl

    def encode(self) -> bytes:
        return bytes([MEV_PSGNOISE, self.ctrl & 0xFF])

    def validate(self, route):
        if route != CHROUTE_PSGN:
            raise PackError(f"PsgNoise on non-noise route {route}")
        if not (0xE0 <= self.ctrl <= 0xEF):
            raise PackError(f"PsgNoise ctrl {self.ctrl:#x} out of range $E0..$EF")


class Detune(Event):
    """Fine pitch detune: the engine adds the signed sc_detune to the looked-up
    fnum (FM, block-corrected) / divisor (PSG) at the next note-on, folded into
    sc_base_freq so vibrato/portamento inherit it. Sub-semitone offset for
    unison/chorus. FM and PSG. Zero-tick (state-only setter)."""
    def __init__(self, detune: int):
        self.detune = detune

    def encode(self) -> bytes:
        return bytes([MEV_DETUNE, self.detune & 0xFF])

    def validate(self, route):
        if not (-128 <= self.detune <= 127):
            raise PackError(f"Detune {self.detune} out of signed byte range -128..127")


class Comm(Event):
    """MEV_EXT sub-op 0: write the operand to SND_STAT_COMM (the score-authored
    cue byte, 68k-visible via Sound_GetComm). Lets the score signal the game at
    musically-authored moments (loop points, stingers, beat marks). Zero-tick.
    Any route. The first MEV_EXT tenant."""
    def __init__(self, val: int):
        self.val = val

    def encode(self) -> bytes:
        return bytes([MEV_EXT, MEV_EXT_COMM, self.val & 0xFF])

    def validate(self, route):
        if not (0 <= self.val <= 255):
            raise PackError(f"Comm val {self.val} out of byte range 0..255")


class Porta(Event):
    """Portamento: set the glide rate (fnum/divisor units per frame; 0 = off). The
    engine glides each new note from the previous pitch to the new one. FM and PSG.
    Must follow at least one normal note on the channel (seeds the glide start).
    Zero-tick."""
    def __init__(self, rate: int):
        self.rate = rate

    def encode(self) -> bytes:
        return bytes([MEV_PORTA, self.rate & 0xFF])

    def validate(self, route):
        if not (0 <= self.rate <= 0xFF):
            raise PackError(f"Porta rate {self.rate} out of byte range 0..255")


class Lfo(Event):
    """Global hardware LFO: write YM2612 $22 (bit3 = enable, bits 0-2 = rate;
    0 disables). Per-channel depth rides each voice's $B4 AMS/FMS bits (Pan
    event / patch) — this is only the master oscillator switch. GLOBAL though
    it rides one channel's stream. Zero-tick (immediate register write)."""
    def __init__(self, value: int):
        self.value = value

    def encode(self) -> bytes:
        return bytes([MEV_LFO, self.value & 0x0F])

    def validate(self, route):
        if not (0 <= self.value <= 0x0F):
            raise PackError(f"Lfo value {self.value:#x} out of range 0..$0F "
                            f"(bit3 enable | bits0-2 rate)")


class Tempo(Event):
    """Global tempo: set the tempo mod (S3K TempoWait units — the RAW per-frame
    accumulator addend; 0 = full speed / tick every frame, BIGGER = SLOWER;
    event-tick rate = (256 - mod)/256). GLOBAL — affects every channel though it
    rides one channel's stream; snaps base/cur/target AND writes through to every
    channel's sc_tempo_mod (instant authored change). Zero-tick (state-only
    setter)."""
    def __init__(self, mod: int):
        self.mod = mod

    def encode(self) -> bytes:
        return bytes([MEV_TEMPO, self.mod & 0xFF])

    def validate(self, route):
        # 0..$FE: 0 is a VALID mod now (full speed — the old "engine clamps
        # 0 -> 16" rule died with the decrement model; a 0 mod never carries so
        # it can never freeze). $FF stays excluded — it is the SND_TEMPO_RESTORE
        # mailbox sentinel and a 1-tick-per-256-frames rate is never authored.
        if not (0 <= self.mod <= 0xFE):
            raise PackError(f"Tempo mod {self.mod} out of authored range 0..254")


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
        # D1: the noise channel has no tone divisor. Psg_ApplyMod would sum the
        # modulation accumulator onto sc_base_freq and re-emit it, so on the noise
        # route the swept word lands on the SN76489 NOISE CONTROL register instead
        # of a frequency latch — it re-triggers the LFSR and walks the mode/rate
        # bits. The runtime gate for this was written and REVERTED for Z80 space
        # (see the note in sound_sequencer.emp's MEV_MODSET handler); the
        # producer-side rule closes the corruption path for all future content at
        # zero Z80 bytes. Author MEV_PSGNOISE for noise mode/rate instead.
        if route == CHROUTE_PSGN:
            raise PackError("ModSet on noise route — pitch-mod corrupts the "
                            "noise control register (D1); author PsgNoise instead")
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
    def __init__(self, route: int, events: list, macro_body=None):
        self.route = route
        self.events = events
        # Optional slot[1] macro stream (a list of MacEvent). None/[] = NULL
        # mod_ptr (single-stream). When present, pack_song lays the body out
        # after the slot[0] command streams and emits a non-NULL header mod_ptr.
        self.macro_body = macro_body


class SongDesc:
    def __init__(self, tempo: int, channels: list, flags: int = 0,
                 tempo_mod: int = None, pitchtable=None):
        self.tempo = tempo
        self.channels = channels
        self.flags = flags          # SH_FLAGS byte (SH_F_* OR'd); pack_song force-sets SH_F_STREAM
        # Optional per-song pitch table the song carries in its own bank (a
        # streaming song with a custom fnum table). The packer does NOT read this
        # field — pack_song takes the resolved BE pitchtable_offset as a separate
        # argument — so it is metadata that a caller (e.g. convert_song) attaches
        # for the song_table/loader to wire up. None = use the engine default
        # pitch table (the SongHeader pitchtable_ptr stays 0).
        self.pitchtable = pitchtable
        # Phase 3 / H.4: tempo mod — the RAW S3K TempoWait addend (SMPS header
        # pass-through). Per frame the engine does `accum += mod`; a CARRY frame
        # is a tempo-delay (no event-tick), a no-carry frame runs exactly one
        # event-tick. Event-tick rate = (256 - mod)/256 ticks/frame, so 0 = full
        # speed (tick every frame; the default) and bigger = slower. This
        # replaced the old quantizing `tempo_base` reload model (rate 16/N),
        # whose 1/N granularity mis-played HCZ2 by -1.42%. pack_song
        # hard-validates the final value (0..255) rather than clamping.
        self.tempo_mod = 0 if tempo_mod is None else tempo_mod


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
            if repeat_depth > 0:
                raise PackError(
                    "nested RepeatStart: the engine keeps ONE sc_repeat_ptr/"
                    "sc_repeat_count per channel (single-level repeats only — "
                    "sound_sequencer.asm Seq_Op_RepeatStart); a nested body "
                    "would overwrite the saved pointer and corrupt the loop")
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
        enc = ev.encode()
        if enc and enc[0] in _MUSIC_ILLEGAL_OPCODES:
            op = enc[0]
            raise PackError(
                f"opcode {op:#x} is music-illegal (the engine dispatch-folds/"
                f"drops it on a music route) — refusing to emit it")
        stream += enc
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
    leaves the engine-default table in use."""
    if not (0 <= song.tempo <= 0xFF):
        raise PackError(f"tempo {song.tempo} out of byte range")
    # tempo_mod is a raw byte: ANY 0..255 value is a valid S3K TempoWait addend
    # (0 = full speed .. 255 = 1 tick per 256 frames). The old ">= 16" floor
    # guarded the retired reload model's borrow-loop; no such hazard exists in
    # the add/carry model, so only the byte range is enforced.
    if not (0 <= song.tempo_mod <= 0xFF):
        raise PackError(
            f"tempo_mod {song.tempo_mod} out of byte range 0..255")
    if not (0 <= song.flags <= 0xFF):
        raise PackError(f"flags {song.flags} out of byte range")
    # SH_F_STREAM is FORCE-SET: every song streams from ROM (the engine's COPY
    # load path was deleted — budget A.1). The bit stays reserved in the header
    # contract and the packer, as the format authority, guarantees it is set.
    flags = song.flags | SH_F_STREAM
    # Layer 7: adaptive FM6 time-share REQUIRES FM6 to be an FM voice (SH_F_FM6_FM).
    # Without FM6_FM the trigger/exhaust would toggle $2B on a song that never
    # plays FM6 music. Catch the malformed combo at pack time, not on hardware.
    if (flags & SH_F_FM6_ADAPTIVE) and not (flags & SH_F_FM6_FM):
        raise PackError("SH_F_FM6_ADAPTIVE requires SH_F_FM6_FM (FM6 must be an FM voice to time-share with the DAC)")
    if not (1 <= len(song.channels) <= CHROUTE_COUNT):
        raise PackError(
            f"channel_count {len(song.channels)} out of range 1..{CHROUTE_COUNT} "
            f"(the engine has {CHROUTE_COUNT} channel routes; more would load "
            f"as a corrupt/silent song)")
    routes = [ch.route for ch in song.channels]
    if len(set(routes)) != len(routes):
        dupes = sorted({r for r in routes if routes.count(r) > 1})
        raise PackError(
            f"duplicate channel route(s) {dupes} — two streams would fight "
            f"over one chip channel")
    if not (0 <= pitchtable_offset <= 0xFFFF):
        raise PackError(
            f"pitchtable_offset {pitchtable_offset} out of 16-bit range")

    streams = [_validate_channel(ch) for ch in song.channels]

    n = len(song.channels)
    # Phase 3 C-ready header:
    #   flags, tempo, tempo_mod, count, dw pitchtable_ptr,
    #   (route + dw cmd_ptr + dw mod_ptr)*n, dw patch_table_ptr.
    header_len = 4 + 2 + 5 * n + 2

    # Command-stream (slot[0]) offsets relative to blob start.
    offsets = []
    cur = header_len
    for s in streams:
        offsets.append(cur)
        cur += len(s)

    # Macro bodies (slot[1]) lay out AFTER all command streams. Each body's
    # base offset is known here, so MacLoop targets + the Macro() slot[0]
    # operand + the header mod_ptr all resolve to it (back-patch).
    mod_offsets = [0] * n                # 0 = NULL (single-stream channel)
    macro_bodies = [b""] * n
    for i, ch in enumerate(song.channels):
        body_evs = getattr(ch, "macro_body", None)
        if not body_evs:
            continue
        body_base = cur
        body = emit_macro_body(body_evs, body_base)
        # Back-patch every Macro() event in this channel's slot[0] stream to
        # point at this body. (Multiple Macro() arms re-point the same body.)
        for ev in ch.events:
            if isinstance(ev, Macro):
                ev.body_offset = body_base
        mod_offsets[i] = body_base
        macro_bodies[i] = body
        cur += len(body)

    # A slot[0] Macro() with NO macro_body would pack its operand as offset 0
    # (the song header) and MacroTick would execute header bytes as tags.
    for ch, mod in zip(song.channels, mod_offsets):
        if mod == 0 and any(isinstance(ev, Macro) for ev in ch.events):
            raise PackError(
                f"channel (route {ch.route}) stream contains Macro() but the "
                f"channel has no macro_body — the $F9 operand would pack as "
                f"offset 0 and the Z80 would execute the song header")

    # All header/operand pointers are 16-bit BE blob offsets; a blob whose
    # layout runs past $FFFF would silently truncate them.
    if cur > 0xFFFF:
        raise PackError(
            f"song blob layout is {cur} bytes — stream/body offsets exceed the "
            f"16-bit pointer range ($FFFF)")

    # Re-encode the command streams AFTER back-patching Macro operands (the
    # first pass above encoded Macro() with body_offset=0).
    streams = [_validate_channel(ch) for ch in song.channels]

    out = bytearray()
    out.append(flags & 0xFF)
    out.append(song.tempo & 0xFF)
    out.append(song.tempo_mod & 0xFF)
    out.append(n & 0xFF)
    out.append((pitchtable_offset >> 8) & 0xFF)   # pitchtable_ptr hi (BE)
    out.append(pitchtable_offset & 0xFF)          # pitchtable_ptr lo (0 = default)
    for ch, off, mod in zip(song.channels, offsets, mod_offsets):
        out.append(ch.route & 0xFF)
        out.append((off >> 8) & 0xFF)   # cmd_ptr big-endian
        out.append(off & 0xFF)
        out.append((mod >> 8) & 0xFF)   # mod_ptr big-endian (0 = NULL slot[1])
        out.append(mod & 0xFF)
    out.append(0x00)                    # patch_table_ptr hi (wired by loader)
    out.append(0x00)                    # patch_table_ptr lo
    for s in streams:
        out += s
    for body in macro_bodies:
        out += body
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


def bin_path_for(asm_path: str) -> str:
    """Sibling .bin path for a generated .asm path (same stem, .bin extension).
    Shared convention across every emitter's --emit-bin mode (song_packer,
    zyrinx_player, smps_import, sfx_transcode); the .bin is the single-source
    payload the sigil build BINCLUDEs (the .asm twins retired at the flip)."""
    root, _ext = os.path.splitext(asm_path)
    return root + ".bin"


def write_bin(song: SongDesc, out_path: str, pitchtable_offset: int = 0) -> None:
    """Write the EXACT payload bytes pack_song() computes (no labels, no
    align padding) to out_path. This is the single-source blob the sigil build
    BINCLUDEs (the .emp `embed`/BINCLUDE path)."""
    blob = pack_song(song, pitchtable_offset=pitchtable_offset)
    with open(out_path, "wb") as f:
        f.write(blob)
