#!/usr/bin/env python3
"""
Zyrinx "Advanced Z80 Player" REFERENCE PLAYER (The Adventures of Batman & Robin).

Simulates the reverse-engineered Zyrinx sound driver playing "Moving Trucks"
(music-test 13 = Bank2 song4 @ ROM $1F0BDF) frame-by-frame and produces:
  (a) a rendered VGM  (/tmp/mt_player.vgm)         -- YM2612 register writes with timing
  (b) a per-channel musical-event dump (/tmp/mt_player_events.json) for engine porting

Authoritative spec: /tmp/zyrinx_re_{commands,timing_pitch,layout,modulation}.md

The driver model (verified against the driver binary, see comments):
  * Song body = 6 consecutive per-channel blocks: [count][loopback][count x 4-byte entries].
  * Pattern entry = [seq_index, transpose(signed), repeat, tempo].
  * Sequences resolved through the Bank2 seq pointer table @ ROM $1F0F37.
  * Music frame ~59.4 Hz (odd frame). Per channel: IX+33 -= 16/frame; on borrow IX+33 += tempo_base
    and one "event tick" fires. WAIT byte W ($80-$FF) waits ($FF - W) event ticks.
  * Two dispatch tables: Table-1 for the first command after a WAIT, Table-2 for subsequent
    commands in the same tick. Table-1 $00-$08 = PITCH-envelope SETUP (arms key-on); Table-2
    $00-$08 = NOTE trigger that just terminates the group (note already armed by PITCH).
  * Driver channel index C is bound 1:1 to YM channel C (verified at driver $0CE9:
    'LD A,B; CP 3; JR C -> port0 ; else port1, SUB 3' -- B is the driver channel index).
    The CH-select command ($20-$2E) only affects the $0E5E key-latch quirk at $0B3D, NOT the
    freq/TL channel. For Moving Trucks every note plays on YM channel == driver channel.
  * Pitch -> (A4,A0) via the 132-entry table (§2.4), index = clamp(note + transpose).
  * Key-on happens whenever a PITCH command sets keyon_pending; the computed A4/A0 reach the
    chip at that (re)key. Fast trills/arps are realized by frequent re-articulation in the data.

  CORRECTION to the modulation RE doc: the steady-state path ($0CDF->$0CE9->$0CF7->$0DDC)
  RE-EMITS A4/A0 (frequency) EVERY FRAME, not only at key-on (verified in the driver disasm
  and against the oracle, which rewrites A4/A0 at 59.4 Hz for held notes). This means the
  $0A-$12 portamento glide IS audible on a sustained note (the gliding fnum is rewritten each
  frame). It does NOT change which notes play or when -- the musical events (key-ons, note
  transitions) are unchanged -- so the key-on event dump remains the correct port artifact.
  This player emits one event per key-on (note transition); the per-frame re-assertion is a
  rendering detail, optionally expanded into glide sub-steps for $0A notes.
"""

import json
import struct
import sys

ROM_PATH = "/home/volence/sonic_hacks/The Adventures of Batman and Robin/Adventures of Batman & Robin, The (USA).md"
# Moving Trucks = music-test 13 = game-song-index id 13 = B&R Bank2 song4.
# (The OLD targets — Bank1 song3 $1E886F / seqtbl $1E91E3 / voicetbl $1ECC8C — were
#  the WRONG song; their PITCH points were in the wrong octave (40/52 etc). Bank2
#  song4's early PITCH points are 28-34 ($1C-$22), which map DIRECTLY to the oracle's
#  low-octave melody with no octave correction.)
SEQ_PTR_TABLE = 0x1F0F37      # Bank2 SEQ table: 154 x 3-byte [bank, z80_hi, z80_lo]
SONG_ADDR = 0x1F0BDF          # Moving Trucks song body (Bank2 song4; 424 bytes,
                              # 6 channel blocks, counts 17/17/17/18/17/17)
VOICE_PTR_TABLE = 0x1F49A8    # Bank2 VOICE table: 248 x 3-byte [bank,hi,lo] -> 30B patch
N_CHANNELS = 6

FODD = 59.38                  # empirical music-frame (odd-frame) rate, Hz  (doc §1.6)
VGM_SR = 44100                # VGM sample rate
YM_CLOCK = 7670453            # matches the oracle's reported YM2612 clock

# ----------------------------------------------------------------------------
# §2.4 note -> (A4, A0) table, index 0..0x83
# ----------------------------------------------------------------------------
# Canonical octave fnums (idx 0x24..0x2F) -- the 12 chromatic fnums.
_CANON = [0x400, 0x43D, 0x47D, 0x4C2, 0x50A, 0x557, 0x5A8, 0x5FE, 0x659, 0x6BA, 0x721, 0x78D]
# Low octave fnums (idx 0x00..0x23), block stays 0, fnum halved progressively (from §2.4 dump).
_LOW = [128, 135, 143, 152, 161, 170, 181, 191, 203, 215, 228, 241,
        256, 271, 287, 304, 322, 341, 362, 383, 406, 430, 456, 483,
        512, 542, 574, 609, 645, 683, 724, 767, 812, 861, 912, 966]


def build_pitch_tables():
    """Return (A4[], A0[], block[], fnum[]) indexed 0..0x83, plus a reverse (block,fnum)->idx.

    This hand-transcribed §2.4 table is cross-checked against the oracle: the bass
    indices ($1C/$28/$34/$40) render to C1/C2/C3/C4 exactly as the oracle writes them.
    (A ROM table at $1E7000/$1E7100 holds the same fnum value-SET but at indices
    shifted ~4 semitones -- it is NOT the LUT these source indices use; do not swap
    to it. The remaining per-channel octave error on the percussion/FM2 voice is NOT
    in this table.)"""
    a4 = [0] * 0x84
    a0 = [0] * 0x84
    block = [0] * 0x84
    fnum = [0] * 0x84
    for idx in range(0, 0x24):
        f = _LOW[idx]
        block[idx] = 0
        fnum[idx] = f
        a4[idx] = (f >> 8) & 7
        a0[idx] = f & 0xFF
    for idx in range(0x24, 0x84):
        b = (idx - 0x24) // 12
        f = _CANON[(idx - 0x24) % 12]
        block[idx] = b
        fnum[idx] = f
        a4[idx] = (b << 3) | ((f >> 8) & 7)
        a0[idx] = f & 0xFF
    rev = {}
    for idx in range(0x84):
        rev[(block[idx], fnum[idx])] = idx
    return a4, a0, block, fnum, rev


A4_TBL, A0_TBL, BLOCK_TBL, FNUM_TBL, REV_TBL = build_pitch_tables()


# ----------------------------------------------------------------------------
# Engine pitch-table emitter (Sound Phase 3 Task 3).
# Dumps the 132-entry chromatic fnum table (§2.4) to a Z80-syntax .asm the engine
# blob includes as the per-song / engine-default pitch table. LAYOUT (matches
# sound_constants.asm PITCHTAB_*): TWO PARALLEL PAGES — the A4 page (132 bytes,
# the YM $A4 = (block<<3)|fnumHi values) FIRST, then the A0 page (132 bytes, the
# YM $A0 = fnum-low values). So index i: $A4 = page[i], $A0 = page[132 + i]. This
# mirrors Zyrinx's native $0F00 (A4) / $1000 (A0) split. The values are read DIRECTLY
# from the real Zyrinx table in the B&R ROM (build_pitch_tables, PITCHTAB_A4/A0_ADDR),
# so every Moving-Trucks pitch write maps to the oracle's exact entry.
# ----------------------------------------------------------------------------
PITCHTAB_COUNT = 0x84            # 132 entries (idx $00..$83); mirror of PITCHTAB_COUNT

# Index->note anchors for the generated .asm comment, computed from the real table.
def _note_anchors():
    if not FNUM_TBL:
        return {}
    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    out = {}
    for idx in (0x2C, 0x34, 0x40, 0x44):     # a few C/landmark indices
        b = BLOCK_TBL[idx]
        f = FNUM_TBL[idx]
        # crude semitone-from-C2(1290) label is enough for a comment
        out[idx] = "block%d fnum%d" % (b, f)
    return out

_NOTE_ANCHORS = _note_anchors()


def _hexrow(vals, directive="db"):
    if directive == "db":                     # Z80-syntax byte literals
        return ", ".join("0%02Xh" % (v & 0xFF) for v in vals)
    return ", ".join("$%02X" % (v & 0xFF) for v in vals)   # 68k dc.b literals


def emit_pitchtable_asm(label="MovingTrucks_PitchTable", directive="db"):
    """Return the .asm text for the 132-entry two-page (A4 then A0) pitch table.

    directive: "db" (Z80 phase-0 blob context — the engine-default inline copy) or
    "dc.b" (68k ROM data area — the per-song streaming-block copy)."""
    assert len(A4_TBL) == PITCHTAB_COUNT and len(A0_TBL) == PITCHTAB_COUNT
    lines = []
    lines.append("; " + "=" * 70)
    lines.append("; data/sound/movingtrucks_pitchtable.asm — GENERATED by")
    lines.append("; tools/zyrinx_player.py (emit_pitchtable_asm) — DO NOT EDIT BY HAND.")
    lines.append("; Regenerate: python3 tools/zyrinx_player.py --emit-pitchtable")
    lines.append(";")
    lines.append("; The exact Zyrinx \"Moving Trucks\" 132-entry chromatic fnum table")
    lines.append("; (/tmp/zyrinx_re_timing_pitch.md §2.4). Z80-syntax, included INSIDE the")
    lines.append("; phase-0 Z80 blob so Fm_NoteFromTable reads it with direct addressing.")
    lines.append(";")
    lines.append("; LAYOUT (sound_constants.asm PITCHTAB_*): TWO PARALLEL PAGES.")
    lines.append(";   page 0  = A4 bytes (YM $A4 = (block<<3)|fnumHi), %d entries" % PITCHTAB_COUNT)
    lines.append(";   page 1  = A0 bytes (YM $A0 = fnum low),          %d entries" % PITCHTAB_COUNT)
    lines.append(";   For note index i (0..$83):  $A4 = base[i], $A0 = base[%d + i]." % PITCHTAB_COUNT)
    lines.append(";")
    lines.append("; Index->note anchors (idx $24..$83 = a clean 6-octave chromatic run,")
    lines.append("; block = (idx-$24)/12; idx $00..$23 are the sub-octaves, block 0, fnum>>):")
    for idx in sorted(_NOTE_ANCHORS):
        lines.append(";   idx $%02X = %s -> A4=$%02X A0=$%02X"
                     % (idx, _NOTE_ANCHORS[idx], A4_TBL[idx], A0_TBL[idx]))
    lines.append("; " + "=" * 70)
    lines.append("")
    lines.append("%s:" % label)
    lines.append("; --- page 0: A4 (block|fnumHi) bytes, idx $00..$83 ---")
    for i in range(0, PITCHTAB_COUNT, 12):
        lines.append("        %-7s " % directive
                     + _hexrow(A4_TBL[i:i + 12], directive))
    lines.append("; --- page 1: A0 (fnum low) bytes, idx $00..$83 ---")
    for i in range(0, PITCHTAB_COUNT, 12):
        lines.append("        %-7s " % directive
                     + _hexrow(A0_TBL[i:i + 12], directive))
    lines.append("%s_End:" % label)
    lines.append("")
    return "\n".join(lines)


def write_pitchtable_asm(out_path, label="MovingTrucks_PitchTable", directive="db"):
    with open(out_path, "w") as f:
        f.write(emit_pitchtable_asm(label, directive))
        f.write("\n")
    return out_path


def pack_pitchtable() -> bytes:
    """Return the EXACT payload bytes emit_pitchtable_asm's two dc.b/db pages
    encode: PITCHTAB_COUNT A4 bytes followed by PITCHTAB_COUNT A0 bytes (see
    emit_pitchtable_asm's LAYOUT comment). No labels — just the blob a
    --emit-bin / BINCLUDE would carry."""
    assert len(A4_TBL) == PITCHTAB_COUNT and len(A0_TBL) == PITCHTAB_COUNT
    return bytes(b & 0xFF for b in A4_TBL) + bytes(b & 0xFF for b in A0_TBL)


def write_pitchtable_bin(out_path) -> str:
    with open(out_path, "wb") as f:
        f.write(pack_pitchtable())
    return out_path


def emit_pitchtable_emp():
    """Return the .emp text for the banked SndDefaultPitchTable head — the
    132-entry two-page (A4 then A0) pitch table as a self-contained cpu:z80
    data section sigil lowers to movingtrucks_pitchtable.bin (BINCLUDE'd by
    soundBankHead at VMA $8357). Mirrors the sound_tables_z80.emp
    generator-emits-.emp precedent; SHAPE-INVARIANT."""
    assert len(A4_TBL) == PITCHTAB_COUNT and len(A0_TBL) == PITCHTAB_COUNT
    lines = []
    lines.append("// " + "=" * 70)
    lines.append("// games/sonic4/data/sound/movingtrucks_pitchtable.emp — the banked")
    lines.append("// SndDefaultPitchTable / MovingTrucks_PitchTable head (the fallback pitch")
    lines.append("// table sound_fm reads when a song's pitchtable_ptr is 0).")
    lines.append("// GENERATED by tools/zyrinx_player.py (emit_pitchtable_emp) — DO NOT EDIT BY HAND.")
    lines.append("// Regenerate: python3 tools/zyrinx_player.py --emit-pitchtable")
    lines.append("//")
    lines.append("// The exact Zyrinx \"Moving Trucks\" 132-entry chromatic fnum table")
    lines.append("// (/tmp/zyrinx_re_timing_pitch.md §2.4). BANKED at the engine-table head")
    lines.append("// (soundBankHead, VMA $8357, physically in the $58000 bank); sigil lowers")
    lines.append("// this to movingtrucks_pitchtable.bin and soundBankHead BINCLUDE's it.")
    lines.append("// SHAPE-INVARIANT (264 bytes both shapes); the AS-side size guard in")
    lines.append("// sound_bank.inc covers body-length drift.")
    lines.append("//")
    lines.append("// LAYOUT (sound_constants.asm PITCHTAB_*): TWO PARALLEL PAGES.")
    lines.append("//   page 0  = A4 bytes (YM $A4 = (block<<3)|fnumHi), %d entries" % PITCHTAB_COUNT)
    lines.append("//   page 1  = A0 bytes (YM $A0 = fnum low),          %d entries" % PITCHTAB_COUNT)
    lines.append("//   For note index i (0..$83):  $A4 = base[i], $A0 = base[%d + i]." % PITCHTAB_COUNT)
    lines.append("// " + "=" * 70)
    lines.append("")
    lines.append("module data.movingtrucks_pitchtable (cpu: z80)")
    lines.append("")
    lines.append("section movingtrucks_pitchtable (cpu: z80, vma: $8357) {")
    lines.append("    proc MovingTrucks_PitchTable () clobbers() {")
    lines.append("        // --- page 0: A4 (block|fnumHi) bytes, idx $00..$83 ---")
    for i in range(0, PITCHTAB_COUNT, 12):
        lines.append("        dc.b    " + _hexrow(A4_TBL[i:i + 12], "dc.b"))
    lines.append("        // --- page 1: A0 (fnum low) bytes, idx $00..$83 ---")
    for i in range(0, PITCHTAB_COUNT, 12):
        lines.append("        dc.b    " + _hexrow(A0_TBL[i:i + 12], "dc.b"))
    lines.append("    }")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def write_pitchtable_emp(out_path):
    with open(out_path, "w") as f:
        f.write(emit_pitchtable_emp())
    return out_path


def clamp_note(idx, transpose):
    """idx = clamp(note + transpose) into legal 0..0x83 range.

    Driver uses $1100 (positive transpose: saturate to 0x83) / $1200 (negative: saturate to 0x84).
    Both effectively clamp the combined index into the valid table range.
    """
    n = idx + transpose
    if n < 0:
        n = 0
    if n > 0x83:
        n = 0x83
    return n


# ----------------------------------------------------------------------------
# §2.7 PITCH-GLIDE trajectory (cmds $0A-$12). RECONSTRUCTED from the driver disasm
# $029C/$0A99 and validated against the oracle VGM (Moving Trucks). The Zyrinx
# glide is a per-frame 16-bit fnum slide RE-ARTICULATED per re-key; sampling the
# gliding accumulator at successive phases produces a chromatic arpeggio that IS
# the recognizable melody. The native emitter (walk_body) emits this trajectory as
# a run of MEV_PITCHENV note indices instead of dropping the glide.
#
# Two derived tables (the driver's $1300 fnum<<5 and $1400 block<<3):
#   GLIDE_FNUM16[i] = FNUM_TBL[i] << 5   (16-bit accumulator unit)
#   GLIDE_BLOCK8[i] = BLOCK_TBL[i] << 3
# ----------------------------------------------------------------------------
GLIDE_FNUM16 = [FNUM_TBL[i] << 5 for i in range(0x84)] if FNUM_TBL else []
GLIDE_BLOCK8 = [BLOCK_TBL[i] << 3 for i in range(0x84)] if BLOCK_TBL else []

# Block-0 region of the table (idx whose block == 0), sorted by fnum, for the
# OCTAVE rule below. RESOLVED empirically vs the oracle: the gliding accumulator's
# fnum (accum>>5) lands in the low-octave fnum band (645..1933); the oracle plays
# the glide arpeggio at BLOCK 0 (16-49 Hz), NOT at the reconstruction's raw aligned
# block (1-3) which is an octave (or three) too high. So every glide sample is
# reverse-mapped to the nearest BLOCK-0 table index. This is the fix for the
# "octave-too-high, sparse static endpoints" bug — the emitted notes now match the
# oracle's low-octave chromatic melody.
_GLIDE_B0 = sorted((FNUM_TBL[i], i) for i in range(0x84) if BLOCK_TBL[i] == 0) if FNUM_TBL else []


def glide_nearest_b0_idx(fnum):
    """Reverse-map a gliding accumulator fnum (accum>>5) to the nearest BLOCK-0
    canonical pitch-table index (the sounding-octave rule, see above)."""
    best = None
    for f, i in _GLIDE_B0:
        d = abs(f - fnum)
        if best is None or d < best[0]:
            best = (d, i)
    return best[1]


def _glide_slope16(diff, dur):
    """Signed 16/16 integer divide matching the driver's slope computation."""
    if dur <= 0:
        dur = 1
    return diff // dur if diff >= 0 else -((-diff) // dur)


def glide_setup(start_pt, target_pt, transpose, dur_byte, tempo_base):
    """Reconstruct the $029C glide setup. Returns (accum16, slope16, glide_frames).

    start_pt / target_pt = the static PITCH point and the GLIDE target point (note
    numbers); transpose = the per-pattern transpose; dur_byte = the glide command's
    duration operand; tempo_base = the channel tempo (event-tick base).

    glide_frames = (dur_byte * tempo_base) >> 4, min 1.
    Block alignment ($0A99): if start_block <= target_block -> aligned to the start
    octave-shifted into the target block; else target shifted into the start block.
    accum starts at the (aligned) start fnum16; slope = (aligned target - start)/dur.
    """
    start = clamp_note(start_pt, transpose)
    tgt = clamp_note(target_pt, transpose)
    glide_frames = (dur_byte * tempo_base) >> 4
    if glide_frames < 1:
        glide_frames = 1
    sb = GLIDE_BLOCK8[start]
    sf = GLIDE_FNUM16[start]
    tb = GLIDE_BLOCK8[tgt]
    tf = GLIDE_FNUM16[tgt]
    if sb <= tb:                      # ascending/equal: align start up into target block
        asf = sf
        for _ in range((tb - sb) // 8):
            asf >>= 1
        accum = asf & 0xFFFF
        slope = _glide_slope16(tf - asf, glide_frames)
    else:                             # descending: align target down into start block
        af = tf
        for _ in range((sb - tb) // 8):
            af >>= 1
        accum = sf & 0xFFFF
        slope = _glide_slope16(af - sf, glide_frames)
    return accum, slope, glide_frames


def parse_song(rom):
    """Parse Moving Trucks (Bank2 song4) into 6 channel blocks of pattern entries."""
    p = SONG_ADDR
    channels = []
    for ch in range(N_CHANNELS):
        count = rom[p]
        loopback = rom[p + 1]
        p += 2
        entries = []
        for _ in range(count):
            seqi = rom[p]
            tr = rom[p + 1]
            rep = rom[p + 2]
            tempo = rom[p + 3]
            p += 4
            tr_s = tr - 256 if tr >= 128 else tr
            entries.append({"seq": seqi, "transpose": tr_s, "repeat": rep, "tempo": tempo})
        channels.append({"count": count, "loopback": loopback, "entries": entries})
    return channels


def seq_addr(rom, idx):
    base = SEQ_PTR_TABLE
    b = rom[base + idx * 3]
    h = rom[base + idx * 3 + 1]
    l = rom[base + idx * 3 + 2]
    z80 = (h << 8) | l
    return (b << 15) + (z80 - 0x8000)


# ----------------------------------------------------------------------------
# Per-channel state machine
# ----------------------------------------------------------------------------
class Channel:
    def __init__(self, rom, ch_index, block):
        self.rom = rom
        self.ch = ch_index
        self.block = block
        self.count = block["count"]
        self.loopback = block["loopback"]
        self.active = block["count"] > 0

        # tempo accumulator (exact driver model)
        self.tempo_base = 0          # IX+32
        self.tick_accum = 0          # IX+33  (-=16/frame; +=tempo on borrow)
        # IX+34 wait counter: 0 = read events this tick; else INC toward 0 each tick.
        # Stored as the raw driver value: a WAIT byte W sets IX+34 = (W+1)&0xFF.
        self.wait_ctr = 0            # IX+34

        # pattern position
        self.pat_index = -1          # IX+42 (start -1 so first advance lands on loopback/0)
        self.repeat = 1              # IX+40
        self.transpose = 0           # IX+48

        # sequence read pointer (ROM absolute), and start (for LOOP)
        self.seq_ptr = None
        self.seq_start = None

        # pitch envelope
        self.pitch_pts = [0] * 5     # IX+49..53
        self.env_len = 1             # IX+54
        self.env_cursor = 0          # IX+55

        # glide targets (the disputed $0A-$12)
        self.glide_pts = [0] * 5     # IX+56..60
        self.glide_mode = 0          # IX+44 (0 static, 1 glide)
        self.glide_dur = 0

        # voice / pan / op
        self.voice = -1              # IX+62 cache
        self.pan_select = 0xF8       # IX+17
        self.pan_value = 0x00        # IX+19
        self.op_mod = [0, 0, 0, 0]   # IX+9/11/13/15
        self.param = 0xFF            # IX+7
        self.gate = 0                # IX+20

        self.keyon_pending = 0       # IX+63
        # current computed YM bytes
        self.cur_a4 = 0
        self.cur_a0 = 0
        self.cur_note = None

        self.needs_init = True       # IX+61

        # event log (filled during simulation): list of dicts
        self.events = []

        # diagnostics
        self.note_on_seq = []        # ordered (block, fnum, note_idx) of every key-on

    # ---- pattern advance ($0416 init + $046B advance) ----
    def advance_pattern(self):
        """Advance to the next pattern entry (after repeats exhausted). Mirrors $046B-$04DD."""
        ni = self.pat_index + 1
        if ni >= self.count:
            ni = self.loopback
        self.pat_index = ni
        entry = self.block["entries"][ni]
        self.transpose = entry["transpose"]
        self.repeat = entry["repeat"]
        if entry["tempo"] != 0:
            self.tempo_base = entry["tempo"]
            # IX+33 re-aligned by delta -- modelled implicitly (we keep accumulator continuous)
        self.seq_start = seq_addr(self.rom, entry["seq"])
        self.seq_ptr = self.seq_start
        # reset envelope/op state on (re)entry like the driver's $0447 reset
        self.pan_select = 0xF8
        self.pan_value = 0x00
        self.op_mod = [0, 0, 0, 0]

    def loop_sequence(self):
        """LOOP command ($1C, Table-1): rewind to seq start; rep--; on rep==0 advance pattern.

        Driver $0410 -> $0447 reset (rewind, clear pan/op) -> $0467 DEC repeat.
        """
        # $0447 reset: rewind read ptr to seq start
        self.seq_ptr = self.seq_start
        self.pan_select = 0xF8
        self.op_mod = [0, 0, 0, 0]
        # $0467 DEC repeat
        self.repeat -= 1
        if self.repeat != 0:
            return  # replay same sequence
        self.advance_pattern()


def emit_keyon(chan, time_s, note_idx, a4, a0):
    chan.cur_a4 = a4
    chan.cur_a0 = a0
    chan.cur_note = note_idx
    blk = (a4 >> 3) & 7
    fnum = ((a4 & 7) << 8) | a0
    chan.note_on_seq.append((blk, fnum, note_idx))
    chan.events.append({
        "time_s": round(time_s, 5),
        "ym_channel": chan.ch,
        "note_index": note_idx,
        "a4": a4,
        "a0": a0,
        "voice_index": chan.voice,
        "pan": chan.pan_value,
        "op_bias": list(chan.op_mod),
        "event": "on",
    })


def emit_keyoff(chan, time_s):
    chan.events.append({
        "time_s": round(time_s, 5),
        "ym_channel": chan.ch,
        "note_index": chan.cur_note,
        "a4": chan.cur_a4,
        "a0": chan.cur_a0,
        "voice_index": chan.voice,
        "pan": chan.pan_value,
        "op_bias": list(chan.op_mod),
        "event": "off",
    })


def compute_pitch(chan):
    """Static stepped-pitch ($02F5): note = clamp(pitch_pts[cursor] + transpose); look up A4/A0."""
    pt = chan.pitch_pts[chan.env_cursor % chan.env_len]
    idx = clamp_note(pt, chan.transpose)
    return idx, A4_TBL[idx], A0_TBL[idx]


def run_sequence_group(chan, time_s, glide_as_vol):
    """Execute one tick's command group: first cmd via Table-1, rest via Table-2, until a WAIT.

    Sets chan.wait_ticks_remaining when a WAIT byte is hit. Returns when the group yields.
    """
    rom = chan.rom
    first = True
    # A key-on armed by a PITCH command in this group is emitted when the group ends
    # (after VOICE/PAN/OP in the same tick have been applied), matching the driver which
    # keys the channel after the per-tick command group + output routine run.
    pending_keyon = None  # (note_idx, a4, a0)

    def flush_keyon():
        if pending_keyon is not None:
            emit_keyon(chan, time_s, *pending_keyon)

    # safety guard against runaway sequences
    for _ in range(4096):
        b = rom[chan.seq_ptr]
        if b >= 0x80:
            # WAIT byte: IX+34 = (raw + 1) & 0xFF (driver $0352). Counted up to 0 by INC each tick.
            chan.seq_ptr += 1
            chan.wait_ctr = (b + 1) & 0xFF
            flush_keyon()
            return
        op = b
        if first and op <= 0x08:
            # ----- PITCH SETUP (Table 1) : load 1..5 pitch points, arm key-on -----
            cnt = op // 2 + 1
            pts = [rom[chan.seq_ptr + 1 + k] for k in range(cnt)]
            chan.seq_ptr += 1 + cnt
            # interleave fill so cursor reads base+cursor (doc §3.1 / §3 of modulation)
            p = pts + [pts[-1]] * (5 - cnt)
            if cnt == 1:
                chan.pitch_pts = [p[0]] * 5
            elif cnt == 2:
                chan.pitch_pts = [p[0], p[1], p[0], p[1], p[0]]
            elif cnt == 3:
                chan.pitch_pts = [p[0], p[1], p[2], p[0], p[1]]
            elif cnt == 4:
                chan.pitch_pts = [p[0], p[1], p[2], p[3], p[0]]
            else:
                chan.pitch_pts = [p[0], p[1], p[2], p[3], p[4]]
            chan.env_len = cnt
            chan.env_cursor = 0
            chan.glide_mode = 0
            chan.keyon_pending = 0xFF
            # arm key-on: compute pitch now; emit at group end (after VOICE/OP applied)
            idx, a4, a0 = compute_pitch(chan)
            pending_keyon = (idx, a4, a0)
            chan.keyon_pending = 0
            first = False
        elif (not first) and op <= 0x08:
            # ----- Table-2 NOTE trigger: re-key the current pitch, terminate the group -----
            chan.seq_ptr += 1
            # $0A60 stub: rewinds+saves ptr and returns. The note was armed by a prior PITCH;
            # the trigger re-articulates it. Emit a (re)key on the current pitch.
            if pending_keyon is None:
                idx, a4, a0 = compute_pitch(chan)
                pending_keyon = (idx, a4, a0)
            flush_keyon()
            return
        elif op in (0x0A, 0x0C, 0x0E, 0x10, 0x12):
            # ----- VOL/GLIDE setup (the disputed $0A-$12) -----
            lvls = (op - 0x0A) // 2 + 1
            args = [rom[chan.seq_ptr + 1 + k] for k in range(lvls + 1)]
            chan.seq_ptr += 1 + lvls + 1
            dur = args[-1]
            chan.glide_dur = dur
            if glide_as_vol:
                # Interpretation A: VOL envelope (TL deltas) -- does NOT change pitch.
                # We record it but it doesn't move the note; volume modelled as op-bias-like.
                pass
            else:
                # Interpretation B: portamento glide targets -- sets up a pitch slide.
                gp = args[:-1] + [args[-2]] * (5 - lvls)
                if lvls == 1:
                    chan.glide_pts = [gp[0]] * 5
                else:
                    chan.glide_pts = (gp + gp)[:5]
                chan.glide_mode = 1
            first = False
        elif op == 0x14:
            chan.param = rom[chan.seq_ptr + 1]
            chan.seq_ptr += 2
            first = False
        elif op == 0x16:
            chan.seq_ptr += 1
            first = False
        elif op == 0x18:
            v = rom[chan.seq_ptr + 1]
            chan.seq_ptr += 2
            chan.voice = v
            first = False
        elif op == 0x1A:
            # GATE / retrigger flag
            chan.gate = 1
            chan.seq_ptr += 1
            first = False
        elif op == 0x1C:
            # LOOP (Table 1) -- terminates the sequence; loop/advance pattern.
            chan.seq_ptr += 1
            chan.loop_sequence()
            # continue reading from the (possibly new) sequence in the SAME tick ($0413 JP $0339)
            first = True
            continue
        elif op == 0x1E:
            # Table-2 channel-off; Table-1 NOP. We treat as channel-off (key off).
            chan.seq_ptr += 1
            if not first:
                emit_keyoff(chan, time_s)
            first = False
        elif 0x20 <= op <= 0x2E:
            # CH-select: sets $0E5E key-latch selector (no effect on bound YM channel for MT)
            chan.seq_ptr += 1
            first = False
        elif op == 0x30:
            chan.pan_select = 0xF8
            chan.pan_value = 0x00
            chan.seq_ptr += 1
            first = False
        elif op == 0x32:
            chan.pan_select = 0x38
            chan.pan_value = 0x80
            chan.seq_ptr += 1
            first = False
        elif op == 0x34:
            chan.pan_select = 0x38
            chan.pan_value = 0x40
            chan.seq_ptr += 1
            first = False
        elif op == 0x36:
            chan.pan_select = 0x38
            chan.pan_value = 0xC0
            chan.seq_ptr += 1
            first = False
        elif op in (0x38, 0x3A, 0x3C, 0x3E):
            chan.op_mod[(op - 0x38) // 2] = rom[chan.seq_ptr + 1]
            chan.seq_ptr += 2
            first = False
        elif op in (0x40, 0x42) or (0x44 <= op <= 0x5E):
            chan.seq_ptr += 1
            first = False
        else:
            # should not happen
            chan.seq_ptr += 1
            first = False
    flush_keyon()
    return


def simulate(rom, duration_s, glide_as_vol=False):
    channels_data = parse_song(rom)
    channels = [Channel(rom, c, channels_data[c]) for c in range(N_CHANNELS)]
    # initial bootstrap ($0416): pat_index = -1, repeat = 1, tempo from entry[0]'s tempo override.
    for chan in channels:
        if not chan.active:
            continue
        chan.tempo_base = 0
        chan.tick_accum = 0
        chan.needs_init = False
        chan.advance_pattern()  # lands on pattern loopback (0 for MT), loads tempo, seq ptr

    n_frames = int(duration_s * FODD)
    for frame in range(n_frames):
        time_s = frame / FODD
        for chan in channels:
            if not chan.active:
                continue
            # tempo accumulator ($031E-$0326): IX+33 -= 16; borrow (signed <0) => event tick
            chan.tick_accum -= 16
            if chan.tick_accum >= 0:
                continue  # no event tick this frame ($0326 RET NC)
            chan.tick_accum += chan.tempo_base  # $0327 refill
            # ---- event tick fired. WAIT counter logic ($032D-$0338) ----
            if chan.wait_ctr != 0:
                # INC toward 0 ($0334); when it wraps to 0, the NEXT tick reads events.
                chan.wait_ctr = (chan.wait_ctr + 1) & 0xFF
                continue
            # IX+34 == 0 -> read & execute the next command group (until a WAIT)
            run_sequence_group(chan, time_s, glide_as_vol)
    return channels


# ============================================================================
# NATIVE SONG EMITTER (Sound Phase 3 Task 8)
# ============================================================================
# Walk Moving Trucks' real song data (the per-channel pattern lists -> shared
# sequences -> command streams parsed above) and translate it, PRESERVING
# STRUCTURE, into our native sequencer opcode streams (song_packer events). This
# is a real PORT of the song data — NOT a register replay of the oracle VGM.
#
# Structure preserved:
#   * Each of the 6 channels -> one FM route (FM1..FM6, 1:1; the RE confirms each
#     channel binds to YM channel == channel index, NOT via the CH-select cmd).
#   * Each channel = a leading patch/vol setup + LoopPoint + per-pattern bodies +
#     Jump (the whole 16-pattern list loops, matching loopback=0).
#   * Each pattern's resolved sequence body is emitted ONCE wrapped in
#     RepeatStart..RepeatEnd(repeat) (bounded repeat — NOT unrolled).
#
# Command translation (per /tmp/zyrinx_re_commands.md §6):
#   PITCH_n ($00-$08)  -> PitchEnv(count, transposed point indices). The engine
#       suppresses same-pitch re-attacks, so emitting a PITCHENV per Zyrinx PITCH
#       reproduces the re-key DENSITY via that suppression (Task-9 calibrates).
#   VOICE ($18)        -> the build-time MINIMAL-DELTA voice-step: compute the
#       FmPatch register delta from the previous voice. SMALL delta (<= threshold
#       changed regs, all expressible as per-op group writes) -> RegDelta; LARGE /
#       genuine instrument change -> full Patch(local_idx). FIRST voice = Patch.
#   PAN ($30-$36)      -> Pan(b4) (raw Zyrinx pan value = the $B4 byte the driver
#       wrote: off/$00, R/$80, L/$40, C/$C0; matches the oracle's $B4 writes).
#   OP1-4 ($38-$3E)    -> OpBias(physical op, signed val).
#   WAIT ($80-$FF)     -> SetDur($FF-byte) preceding the group's time-advancing
#       PitchEnv (the engine paces PitchEnv by sc_dur_default).
#   LOOP ($1C)         -> the sequence-body terminator (ends the RepeatStart body).
#   GATE ($1A), PARAM ($14), CH-select ($20-$2E), NOP ($16/$40+) -> no-op (the
#       gate/param re-key flags don't change which note plays; CH-select is the
#       $0E5E key-latch quirk, irrelevant to the 1:1 FM routing — see the RE §3.6).
#   VOL ($0A-$12)      -> dropped (the driver has NO real TL envelope — it is a
#       static-per-note TL bias; /tmp/zyrinx_re_modulation.md §0/§9. A faithful
#       port emits no swept TL. The VOL-cmd DURATION is folded out: the following
#       WAIT carries the hold. Logged.)
# ----------------------------------------------------------------------------

# Import the packer events + the Zyrinx-voice -> FmPatch translation (T8 reuses
# zyrinx_port.translate_voice). Support both tools/-on-path and package styles.
try:
    from song_packer import (
        SongDesc, ChannelDesc,
        SetDur, Rest, Vol, Patch, Pan, OpBias, PitchEnv, RegDelta,
        Note, NoteDur, NoteRaw,
        RepeatStart, RepeatEnd, LoopPoint, Jump, NoteFill, Lfo,
        CHROUTE_FM1, CHROUTE_FM5, CHROUTE_FM6,
        SH_F_FM6_FM, SH_F_STREAM,
        reg_sel, RD_GROUP_TL, REGDELTA_GROUP_COUNT,
        REGDELTA_GROUP_SHIFT, REGDELTA_OP_MASK,
        pack_song, bin_path_for,
    )
    from zyrinx_port import translate_voice, FMPATCH_LEN, emit_patch_bank_asm
except ImportError:  # pragma: no cover - alternate import path
    from tools.song_packer import (  # type: ignore
        SongDesc, ChannelDesc,
        SetDur, Rest, Vol, Patch, Pan, OpBias, PitchEnv, RegDelta,
        Note, NoteDur, NoteRaw,
        RepeatStart, RepeatEnd, LoopPoint, Jump, NoteFill, Lfo,
        CHROUTE_FM1, CHROUTE_FM5, CHROUTE_FM6,
        SH_F_FM6_FM, SH_F_STREAM,
        reg_sel, RD_GROUP_TL, REGDELTA_GROUP_COUNT,
        REGDELTA_GROUP_SHIFT, REGDELTA_OP_MASK,
        pack_song, bin_path_for,
    )
    from tools.zyrinx_port import (  # type: ignore
        translate_voice, FMPATCH_LEN, emit_patch_bank_asm)

VOICES_JSON = ("/home/volence/sonic_hacks/The Adventures of Batman and Robin/"
               "disasm/sound/decoded_full/voices.json")

# ch0..5 -> FM1..FM6 (1:1; ch5 -> FM6 via the adaptive FM6 slot, CHROUTE_FM6 = 5).
NATIVE_FM_ROUTES = [CHROUTE_FM1, CHROUTE_FM1 + 1, CHROUTE_FM1 + 2,
                    CHROUTE_FM1 + 3, CHROUTE_FM5, CHROUTE_FM6]

# ----------------------------------------------------------------------------
# #4 GATE ARTICULATION — per-(channel, voice) gate profile (NoteFill frames)
# ----------------------------------------------------------------------------
# The real Zyrinx driver keys notes OFF partway through their slot (gated
# staccato) where our walker's command model played 100% legato — the "muffled
# thud" bass and smeared fast runs. The driver's gate mechanic is not modelled
# by the walker, so the gate lengths are EXTRACTED empirically from the
# authoritative reference capture (mt_ref.vgm): per (channel, voice) the
# keyed-frames/slot-frames histogram is stable across the whole song:
#
#   voice (B0, DT/MUL $30/$34/$38/$3C)        gate     where
#   $2D (08,0C,08,0C)  offbeat bass "bonk"    8 of 14  every channel (ch0/1/3/5)
#   $3C (03,01,07,02)  downbeat bass          17       ch1/2/3: held FULL on its
#                                                      14-frame slots (17 > 14 =
#                                                      legato) but gated 17 of 21
#                                                      on the long slots;
#                                             8 of 14  ch0 outro
#   $35/$3D run family (02|00,00,00,00..05)   5 of 7   every channel (ch0/3/4/5)
#   $28 (08,00,04,02)  pizz/arp groove        5 of 7   ch2/4/5 (LEGATO on ch1,
#                                                      where its slots are 14)
#   $3D (07,07,08,04)  comp stab              8 of 14  ch3 verse ONLY (held full
#                                                      length on ch0/2/4/5)
#   $36 (04,04,33,45)  ch5 run color          5 of 7   ch5
#   everything else (incl. the 113-frame held stabs)   legato (fill 0)
#
# Emission: _Walker._voice() looks the NEW voice up in this channel's table and
# emits NoteFill(n) whenever the gate value changes (NoteFill(0) = back to
# legato). The engine reloads the master into sc_fill_count at every FM key-on
# and keys off when it expires, so slots SHORTER than the gate stay effectively
# legato (e.g. a gate-8 voice's 7-frame slots are keyed the full 7 frames) —
# exactly the reference behavior, so one fill value per (channel, voice) covers
# every slot length that voice plays.
#
# Voice identity = (fp_alg_fb, dt_mul[0:4]) of the translated FmPatch, which
# equals the VGM-observable fingerprint (reg $B0, regs $30/$34/$38/$3C).
_VF_BASS_OFFBEAT = (0x2D, (0x08, 0x0C, 0x08, 0x0C))
_VF_BASS_DOWN    = (0x3C, (0x03, 0x01, 0x07, 0x02))
_VF_PIZZ         = (0x28, (0x08, 0x00, 0x04, 0x02))
_VF_STAB         = (0x3D, (0x07, 0x07, 0x08, 0x04))
_VF_RUN_COLOR    = (0x36, (0x04, 0x04, 0x33, 0x45))
_VF_RUN_FAMILY = (
    (0x35, (0x02, 0x00, 0x00, 0x00)),
    (0x3D, (0x02, 0x00, 0x00, 0x01)),
    (0x35, (0x02, 0x00, 0x00, 0x02)),
    (0x3D, (0x00, 0x00, 0x00, 0x03)),
    (0x3D, (0x00, 0x00, 0x00, 0x04)),
    (0x3D, (0x00, 0x00, 0x00, 0x05)),
)


def _build_gate_tables():
    """Per-source-channel { (alg_fb, dt_mul) -> NoteFill frames } (see above)."""
    tabs = []
    for _ch in range(6):
        t = {_VF_BASS_OFFBEAT: 8, _VF_BASS_DOWN: 17}
        for vf in _VF_RUN_FAMILY:
            t[vf] = 5
        tabs.append(t)
    tabs[0][_VF_BASS_DOWN] = 8       # ch0 outro walk-down is fully gated
    for ch in (2, 4, 5):
        tabs[ch][_VF_PIZZ] = 5       # legato on ch1 (its slots are 14 frames)
    tabs[3][_VF_STAB] = 8            # ch3 verse; legato on ch0/2/4/5
    tabs[5][_VF_RUN_COLOR] = 5
    return tabs


NATIVE_GATE_TABLES = _build_gate_tables()

# Voice-step delta threshold: a VOICE change differing in MORE than this many
# FmPatch register bytes (or in a byte that has no RegDelta encoding, i.e.
# alg_fb/$B0 or lr_ams_fms/$B4) is a GENUINE instrument change -> full Patch.
# Calibrated against the data: the bass voice-step ($9C..$A0) differs by exactly 1
# byte (the S1-TL, $40 group op0) -> RegDelta; the lead swap ($0E vs $A4) differs
# in ~25 bytes -> Patch. 8 is comfortably between (the task's suggested threshold).
VOICE_DELTA_THRESHOLD = 8

# Moving Trucks song format code ($38 = 56) = the Zyrinx per-channel tempo base
# (the original driver's `IX+33 -= 16/frame; on borrow += base` clock -> 16/56 =
# 2/7 event-ticks per frame ~= 16.87 Hz, the Zyrinx ~17 events/sec). The engine
# now runs S3K's exact TempoWait model instead (header tempo_mod: accum += mod
# per frame, carry skips the tick; rate = (256-mod)/256), so the packed header
# carries zyrinx_base_to_tempo_mod(MT_FORMAT_CODE) — see that helper for the
# (tiny, unavoidable) rounding this conversion takes.
MT_FORMAT_CODE = 0x38


def zyrinx_base_to_tempo_mod(base: int) -> int:
    """Zyrinx tempo base (event-tick rate 16/base) -> nearest S3K tempo mod
    (event-tick rate (256 - mod)/256).

    16/base = (256 - mod)/256  ->  mod = 256 - 4096/base.

    EXACT only when base divides 4096. Moving Trucks' base 56 -> mod
    256 - 73.14 -> 183 (rate 73/256 = 0.28516 vs the true 2/7 = 0.28571:
    -0.196%, ~2.3 s/20 min — the closest the 8-bit S3K model can express; the
    alternative mod 182 is +1.17%). Full-speed base 16 -> mod 0 exactly."""
    if base <= 0:
        raise ValueError(f"zyrinx tempo base {base} must be positive")
    return max(0, min(255, 256 - round(4096 / base)))


# ----------------------------------------------------------------------------
# RE-ARTICULATION CADENCE MODEL
# ----------------------------------------------------------------------------
# Our engine re-keys on EVERY MEV_PITCHENV (the same-pitch suppression was removed
# from the engine — correct, per the driver). So the re-key CADENCE must live in
# the DATA: walk_body emits one MEV_PITCHENV per source PITCH-group, paced by that
# group's WAIT byte (SetDur).
#
# For the CORRECT song (Bank2 song4) the cadence is INTRINSIC to the source WAIT
# bytes — no artificial re-key window is needed. Measured per-channel WAIT
# histogram (event-ticks) vs the oracle's measured median key-on IOI:
#     ch0  WAIT 3 dom (168x)  ->  oracle median 2.95 ticks (~174 ms)  ✓
#     ch1  WAIT 3/1 (164/162) ->  oracle median 2.99 ticks (~176 ms)  ✓
#     ch2  WAIT 3 dom (192x)  ->  oracle median 2.95 ticks (~174 ms)  ✓
#     ch3  WAIT 3/1 (136/112) ->  oracle median 2.94 ticks (~173 ms)  ✓
#     ch4  WAIT 0/1 dom       ->  oracle median 1.48 ticks (~ 87 ms)  ✓
#     ch5  WAIT 0/1 dom       ->  oracle median 1.48 ticks (~ 87 ms)  ✓
# The melody changes pitch nearly every group, so same-pitch coalescing almost
# never fires; the WAIT bytes alone reproduce the oracle's per-channel cadence.
# We therefore use a re-key window of 1 tick on ALL channels (= "emit a fresh
# keyed PitchEnv for every source PITCH-group, paced by its WAIT"); the window
# only ever coalesces a genuine zero-WAIT mid-tick repeat of the SAME pitch, which
# is correct (the engine cannot re-key faster than one tick anyway).
#
# (The OLD Bank1-song3-tuned [3,3,3,3,1,1] window was a wrong-song workaround that
# forced an artificial 3-tick floor onto a repeat-heavy stream; the correct song
# does not have that 88-89%-same-pitch repeat structure, so it is removed.)
REKEY_WINDOW_TICKS = [1, 1, 1, 1, 1, 1]   # per source channel (ch0..5)


# ----------------------------------------------------------------------------
# OCTAVE CORRECTION — REMOVED (was a Bank1-song3 wrong-song workaround).
# ----------------------------------------------------------------------------
# The OLD target (Bank1 song3) had PITCH points in the WRONG octave (40/52...),
# rendering up to block 3-4, so a per-channel OCTAVE_BLOCK_CAP forced them down.
# The CORRECT song (Bank2 song4) has PITCH points 14-68 whose canonical blocks are
# already 0-2 — exactly the oracle's measured per-channel band (oracle uses blocks
# 0/1/2 on EVERY channel; ch1's bass even reaches block 1). So NO octave correction
# is applied: octave_cap_idx is an identity pass-through. (If a future oracle diff
# for THIS song proves a per-channel correction is genuinely needed, re-introduce a
# targeted cap here — but the points map directly today.)
_OCTAVE_CAP_DEFAULT = None               # None = no cap (identity)


def octave_cap_idx(idx, cap=_OCTAVE_CAP_DEFAULT):
    """Identity pass-through (octave correction removed for the correct song).
    `cap` is accepted-and-ignored for call-site compatibility; if a real cap value
    (int) is ever passed, it octave-downs to that block ceiling — but the default
    None leaves the directly-mapping Bank2 points untouched."""
    if cap is None:
        return idx
    while idx >= 12 and BLOCK_TBL[idx] > cap:
        idx -= 12
    return idx


def voice_addr(rom, idx):
    """Resolve Bank2 VOICE-table entry `idx` to an absolute ROM address.
    Table @ VOICE_PTR_TABLE = 248 x 3-byte [bank, z80_hi, z80_lo]; same
    z80->ROM resolution as the seq table: (bank<<15)+(z80-0x8000)."""
    base = VOICE_PTR_TABLE
    b = rom[base + idx * 3]
    h = rom[base + idx * 3 + 1]
    l = rom[base + idx * 3 + 2]
    z80 = (h << 8) | l
    return (b << 15) + (z80 - 0x8000)


def decode_voice(rom, idx):
    """Decode a Bank2 30-byte FM patch (resolved via the VOICE pointer table) into
    the same dict shape voices.json uses (so translate_voice consumes it unchanged).

    Patch byte layout (verified against voices.json bank2 — an exact match):
      [0]      fb_algo  -> fb = (b>>3)&7, algo = b&7
      [1..24]  six 4-byte per-operator groups: dt_mul, tl, ks_ar, am_d1r, d2r, sl_rr
               (operator order = Zyrinx natural op1..op4)
      [25]     ams_fms_pan
      [26..29] ext[4]
    """
    a = voice_addr(rom, idx)
    if a < 0 or a + 30 > len(rom):
        # Pointers past the real voice-table extent (idx >= ~235) resolve into
        # unrelated ROM / negative addresses. Moving Trucks references only voices
        # <= 212, so these are never collected into the per-song bank; return a
        # zeroed placeholder so the FULL-bank build does not crash.
        return {"fb": 0, "algo": 0, "dt_mul": [0, 0, 0, 0], "tl": [0, 0, 0, 0],
                "ks_ar": [0, 0, 0, 0], "am_d1r": [0, 0, 0, 0],
                "d2r": [0, 0, 0, 0], "sl_rr": [0, 0, 0, 0],
                "ams_fms_pan": 0, "ext": [0, 0, 0, 0]}
    raw = rom[a:a + 30]
    g = lambda o: [raw[o], raw[o + 1], raw[o + 2], raw[o + 3]]
    return {
        "fb": (raw[0] >> 3) & 7,
        "algo": raw[0] & 7,
        "dt_mul": g(1), "tl": g(5), "ks_ar": g(9),
        "am_d1r": g(13), "d2r": g(17), "sl_rr": g(21),
        "ams_fms_pan": raw[25],
        "ext": [raw[26], raw[27], raw[28], raw[29]],
    }


# B&R Bank2 has 248 VOICE-table entries (the JSON's decoded `bank2` list is shorter
# and is Bank1-era anyway); decode straight from the ROM so the bank is complete and
# authoritative for THIS song.
VOICE_BANK_COUNT = 248


def _load_voice_bank(rom=None):
    """Decode the FULL Bank2 voice bank straight from the ROM (Moving Trucks =
    Bank2 song4). Returns a list of voice dicts indexable by absolute voice idx."""
    if rom is None:
        rom = open(ROM_PATH, "rb").read()
    return [decode_voice(rom, i) for i in range(VOICE_BANK_COUNT)]


def _fmpatch_byte_to_regsel(byte_idx):
    """Map an FmPatch byte index (2..25) to a RegDelta reg_sel, or None for the
    two scalar leads (idx 0 = fp_alg_fb/$B0, idx 1 = fp_lr_ams_fms/$B4) which have
    no per-operator register group (a change there forces a full Patch)."""
    if byte_idx < 2:
        return None                         # $B0 / $B4 -> not RegDelta-encodable
    rel = byte_idx - 2
    group = rel // 4                        # 0..5 = $30/$40/$50/$60/$70/$80
    op = rel % 4                            # 0..3 = physical S1,S3,S2,S4
    if group >= REGDELTA_GROUP_COUNT:
        return None
    return reg_sel(group, op)


def _voice_step_event(prev_fp, new_fp, new_local_idx):
    """Decide the voice-step encoding from the previous voice's FmPatch to the new
    one. Returns (event, kind) where kind is 'patch' or 'regdelta'.

    SMALL delta (<= VOICE_DELTA_THRESHOLD changed regs, ALL RegDelta-encodable)
    -> RegDelta(only the changed registers). LARGE / non-encodable -> full Patch.
    prev_fp None (first voice) always -> Patch.
    """
    if prev_fp is None:
        return Patch(new_local_idx), "patch"
    diffs = [i for i in range(FMPATCH_LEN) if new_fp[i] != prev_fp[i]]
    if not diffs:
        return None, "none"                 # identical voice -> nothing to emit
    pairs = []
    for i in diffs:
        rs = _fmpatch_byte_to_regsel(i)
        if rs is None:                       # $B0/$B4 changed -> must full-reload
            return Patch(new_local_idx), "patch"
        pairs.append((rs, new_fp[i]))
    if len(pairs) > VOICE_DELTA_THRESHOLD:
        return Patch(new_local_idx), "patch"
    return RegDelta(pairs), "regdelta"


def _zyrinx_op_to_phys(op_natural):
    """Zyrinx OP1-4 -> our FmPatch op slot. The ROM voice bytes are already in
    physical-register order and we no longer reorder them (OP_REORDER=identity), so
    a Zyrinx OP_n bias targets FmPatch slot n directly. VERIFIED against the live
    B&R FM2 capture; see zyrinx_port.OP_REORDER."""
    return (0, 1, 2, 3)[op_natural]


def _to_signed(b):
    return b - 256 if b >= 0x80 else b


class _Walker:
    """Translates ONE resolved Zyrinx sequence body (seq start .. first LOOP) into
    our v0 events, preserving the per-tick command groups. Carries the per-channel
    voice state (the previous voice's FmPatch) ACROSS patterns so cross-pattern
    voice-steps are still minimal deltas.

    bank   = the Zyrinx bank-1 voice list (translate_voice consumes its dicts).
    remap  = absolute voice idx -> dense local patch idx (build_native_patch_bank).
    stats  = a per-channel dict the walker tallies opcode counts into.
    """

    def __init__(self, rom, bank, remap, stats):
        self.rom = rom
        self.bank = bank
        self.remap = remap
        self.stats = stats
        self.prev_fp = None            # previous voice's FmPatch (None = no voice yet)
        self.cur_local = None          # current dense local patch idx
        self.first_local = None        # the channel's FIRST voice (leading setup)
        self.porta_dropped = 0         # $0A glide -> plain note count (none in MT)
        self.tempo_base = MT_FORMAT_CODE  # event-tick base (for glide_frames -> ticks)
        self.rekey_window = 3          # per-channel re-key floor (ticks); set per channel
        self.octave_cap = _OCTAVE_CAP_DEFAULT  # per-channel rendered-block ceiling
        # #4 GATE ARTICULATION (see NATIVE_GATE_TABLES): this channel's
        # { (alg_fb, dt_mul) -> NoteFill frames } map, and the last NoteFill value
        # emitted. cur_fill=None = unknown (start of a body) so the body's first
        # VOICE always re-emits its gate — bodies are self-contained (mirroring the
        # per-body prev_fp reset) and the fill is correct on every loop iteration.
        self.gate_table = {}
        self.cur_fill = None

    def first_voice_local(self):
        """Local patch idx of the channel's FIRST voice (for the leading setup
        Patch — the packer wants a Patch before the first keyed note), or 0 if the
        channel references no voice."""
        return self.first_local if self.first_local is not None else 0

    def _voice(self, voice_idx, out):
        """Apply a VOICE change: emit Patch or RegDelta per the minimal-delta rule,
        plus the voice's gate (NoteFill) when it differs from the current one."""
        new_fp = translate_voice(self.bank[voice_idx])
        local = self.remap[voice_idx]
        ev, kind = _voice_step_event(self.prev_fp, new_fp, local)
        self.prev_fp = new_fp
        self.cur_local = local
        if self.first_local is None:
            self.first_local = local
        # #4 GATE ARTICULATION: the gate is a property of the (channel, voice)
        # bucket (NATIVE_GATE_TABLES). Emit NoteFill only on change — it persists
        # in the engine and is reloaded into sc_fill_count at every key-on.
        fill = self.gate_table.get((new_fp[0], tuple(new_fp[2:6])), 0)
        if fill != self.cur_fill:
            out.append(NoteFill(fill))
            self.cur_fill = fill
            self.stats["notefill"] += 1
        if ev is None:
            return
        out.append(ev)
        if kind == "patch":
            self.stats["patch"] += 1
        else:
            self.stats["regdelta"] += 1

    def walk_body(self, seq_start, transpose):
        """Translate one sequence body (seq_start .. the first LOOP $1C) into our
        v0 events by FAITHFULLY simulating the Zyrinx driver's per-tick command
        groups and TWO-TABLE dispatch ($0339 / $03D0 / $0A60).

        A group is read at each event-tick where the WAIT counter is 0. The FIRST
        command of a group dispatches via Table-1, every SUBSEQUENT command via
        Table-2, until the group ends. A group ends on:
          * a WAIT byte W (>=$80): cost = 1 + ($FF - W) event-ticks (the read tick
            plus the silent wait ticks), OR
          * a Table-2 NOTE ($00-$08 that is NOT first-in-group): NoteTrigger_$0A60
            costs exactly 1 event-tick and REWINDS the read pointer (DEC HL) so the
            note byte is re-read by the NEXT group as a Table-1 PITCH. This "orphan
            tick" is what spaces the dense fast lines (seq117/113/121) to one key-on
            per 2 event-ticks, giving every body a 64-tick length so all channels
            share one 2688-tick loop and stay phase-locked. (Charging every $FF
            group as an independent 1-tick onset — the old bug — runs those channels
            ~1.9x too fast and they drift off the grid, off each other.)

        Emission: each Table-1 PITCH group emits one keyed note (PitchEnv); its hold
        is its own tick cost PLUS the trailing NON-onset groups (orphan re-arm /
        GATE / pure WAIT) up to the next onset, so the note sustains across the
        orphan tick and the next PITCH re-keys it. Our engine retriggers the FM
        envelope on every PitchEnv, so the re-key IS the percussive punch the GATE
        flag asks for — no time-bearing note-off REST is needed (and emitting one,
        as the old code did, is exactly what stole ticks and desynced the channels).
        GATE ($1A) is therefore modelled as a ZERO-tick retrigger flag (matching the
        disassembly's Cmd_Gate_$03A1 and the oracle, which keeps a rock-steady onset
        grid while every note is articulated). Zero-tick setters (VOICE / PAN / OP)
        are flushed just before the note they qualify.
        """
        rom = self.rom
        out = []
        p = seq_start
        # Each body is self-contained: force the first VOICE to a full Patch
        # (prev_fp=None) so the opening voice reloads correctly on every loop
        # iteration (the body is what replays; the leading setup runs once).
        # cur_fill mirrors that: the body's first VOICE re-emits its NoteFill.
        self.prev_fp = None
        self.cur_fill = None
        cur_setdur = None      # SetDur of the note currently sounding (extended by
                               #   trailing non-onset groups; None = nothing held)
        setters = []           # zero-tick events buffered for the next emission

        def emit_setters():
            if setters:
                # OpBias MUST precede Patch/RegDelta: the engine applies the per-
                # operator TL bias (sc_opbias) DURING the patch load (Fm_PatchTlGroup
                # adds it to the operator TL). A Patch that loads before the bias is
                # set omits it -> wrong modulator/carrier levels (lost kick punch /
                # wrong timbre). This mirrors the driver, which computes the key-on
                # TL = (0x7F^patch_TL)+op_mod AFTER the group's OP commands. Emit all
                # OpBias first, then the rest (Patch/RegDelta/Pan) in original order.
                ob = [e for e in setters if isinstance(e, OpBias)]
                if ob:
                    out.extend(ob)
                    out.extend(e for e in setters if not isinstance(e, OpBias))
                else:
                    out.extend(setters)
                setters.clear()

        for _group in range(8192):
            # ---- read ONE command group via the two-table dispatch ----
            first = True
            group_is_onset = False     # set by a Table-1 PITCH / GLIDE
            group_points = None        # transposed pitch points for an onset group
            gticks = None
            looped = False
            for _cmd in range(4096):
                b = rom[p]
                if b >= 0x80:                       # WAIT: ends the group
                    gticks = 1 + (0xFF - b)         # read tick + silent ticks
                    p += 1
                    break
                op = b
                if (not first) and op <= 0x08:      # Table-2 NOTE = orphan tick
                    # NoteTrigger_$0A60: cost 1 event-tick, REWIND (do NOT consume);
                    # the byte is re-read next group as a Table-1 PITCH.
                    gticks = 1
                    break
                if op <= 0x08:                       # Table-1 PITCH setup (arms key-on)
                    cnt = op // 2 + 1
                    pts = [rom[p + 1 + k] for k in range(cnt)]
                    p += 1 + cnt
                    group_points = [clamp_note(n, transpose) for n in pts]
                    group_is_onset = True
                    first = False
                elif op in (0x0A, 0x0C, 0x0E, 0x10, 0x12):   # GLIDE (unused by MT)
                    # Moving Trucks references no glides; this is a faithful-enough
                    # fallback for other songs: key the glide TARGET as a plain note
                    # (no smooth per-frame ramp). Consumes N targets + 1 duration.
                    lvls = (op - 0x0A) // 2 + 1
                    args = [rom[p + 1 + k] for k in range(lvls + 1)]
                    p += 1 + lvls + 1
                    group_points = [clamp_note(args[0], transpose)]
                    group_is_onset = True
                    self.porta_dropped += 1
                    first = False
                elif op == 0x14:                     # PARAM (key/legato override) -> drop
                    p += 2
                    first = False
                elif op == 0x16:                     # NOP / buffer sink
                    p += 1
                    first = False
                elif op == 0x18:                     # VOICE
                    self._voice(rom[p + 1], setters)
                    p += 2
                    first = False
                elif op == 0x1A:                     # GATE = zero-tick retrigger flag
                    p += 1
                    first = False
                elif op == 0x1C:                     # LOOP -> body terminator
                    p += 1
                    looped = True
                    break
                elif op == 0x1E:                     # CH-OFF (T2) / NOP (T1) -> drop
                    p += 1
                    first = False
                elif 0x20 <= op <= 0x2E:             # CH-select -> no-op (1:1 routing)
                    p += 1
                    first = False
                elif op == 0x30:                     # PAN_OFF
                    setters.append(Pan(0x00)); self.stats["pan"] += 1
                    p += 1
                    first = False
                elif op == 0x32:                     # PAN_R (raw Zyrinx pan $80)
                    setters.append(Pan(0x80)); self.stats["pan"] += 1
                    p += 1
                    first = False
                elif op == 0x34:                     # PAN_L (raw Zyrinx pan $40)
                    setters.append(Pan(0x40)); self.stats["pan"] += 1
                    p += 1
                    first = False
                elif op == 0x36:                     # PAN_C (raw Zyrinx pan $C0)
                    setters.append(Pan(0xC0)); self.stats["pan"] += 1
                    p += 1
                    first = False
                elif op in (0x38, 0x3A, 0x3C, 0x3E): # OP1-4 TL bias
                    raw = rom[p + 1]
                    p += 2
                    phys = _zyrinx_op_to_phys((op - 0x38) // 2)
                    setters.append(OpBias(phys, _to_signed(raw)))
                    self.stats["opbias"] += 1
                    first = False
                else:                                # $40+ NOP sink
                    p += 1
                    first = False
            else:
                raise RuntimeError("runaway command group (no WAIT/NOTE/LOOP)")

            if looped:
                break

            # ---- emit the group ----
            if group_is_onset:
                emit_setters()
                cap = [octave_cap_idx(x, self.octave_cap) for x in group_points]
                cur_setdur = SetDur(gticks)
                out.append(cur_setdur)
                out.append(PitchEnv(cap))
                self.stats["pitchenv"] += 1
            else:
                # NON-onset group (orphan re-arm / GATE / pure WAIT): extend the
                # currently sounding note across these ticks (it holds through the
                # orphan tick until the next PITCH re-keys it). Setters land mid-note.
                emit_setters()
                if cur_setdur is not None:
                    cur_setdur.ticks += gticks
                elif gticks > 0:
                    # leading silence before the first keyed note -> a genuine rest.
                    out.append(SetDur(gticks))
                    out.append(Rest())
                    self.stats["rest"] += 1
        else:
            raise RuntimeError("runaway sequence walk (no LOOP terminator)")

        emit_setters()
        return out

def _channel_first_voice(rom, block):
    """The FIRST voice index a channel references (scan its patterns' sequence
    bodies to the LOOP), or None if it references no voice."""
    for entry in block["entries"]:
        p = seq_addr(rom, entry["seq"])
        for _ in range(8192):
            b = rom[p]
            if b >= 0x80:
                p += 1
                continue
            if b <= 0x08:
                p += 1 + (b // 2 + 1)
            elif b in (0x0A, 0x0C, 0x0E, 0x10, 0x12):
                p += 1 + ((b - 0x0A) // 2 + 1) + 1
            elif b == 0x14:
                p += 2
            elif b == 0x18:
                return rom[p + 1]
            elif b in (0x38, 0x3A, 0x3C, 0x3E):
                p += 2
            elif b == 0x1C:
                break
            else:
                p += 1
    return None


def collect_native_voices(rom, channels_data):
    """Distinct voice indices the song references, in FIRST-SEEN order (channel ->
    pattern -> sequence-event scan, walking bodies to the LOOP). Determines the
    dense local bank order + the abs-voice -> local-idx remap."""
    seen = set()
    order = []
    for block in channels_data:
        for entry in block["entries"]:
            start = seq_addr(rom, entry["seq"])
            p = start
            for _ in range(8192):
                b = rom[p]
                if b >= 0x80:
                    p += 1
                    continue
                if b <= 0x08:
                    p += 1 + (b // 2 + 1)
                elif b in (0x0A, 0x0C, 0x0E, 0x10, 0x12):
                    p += 1 + ((b - 0x0A) // 2 + 1) + 1
                elif b == 0x14:
                    p += 2
                elif b == 0x18:
                    vi = rom[p + 1]
                    if vi not in seen:
                        seen.add(vi)
                        order.append(vi)
                    p += 2
                elif b in (0x38, 0x3A, 0x3C, 0x3E):
                    p += 2
                elif b == 0x1C:
                    break
                else:
                    p += 1
            else:
                raise RuntimeError("runaway voice scan (no LOOP terminator)")
    return order


def build_native_patch_bank(rom, channels_data, bank):
    """Build the per-song dense FmPatch bank + abs-voice -> local-idx remap.
    Returns (bank_bytes, remap, count)."""
    order = collect_native_voices(rom, channels_data)
    remap = {}
    out = bytearray()
    for vi in order:
        remap[vi] = len(remap)
        out.extend(translate_voice(bank[vi]))
    return bytes(out), remap, len(remap)


def _analyze_body_entry_states(bodies, recs, lead_fp):
    """Loop-aware two-pass dataflow over a channel's emitted body list: compute,
    for every body, the SET of states (voice FmPatch bytes, opbias[4] tuple,
    NoteFill value) the engine can be in when the body's prefix runs.

    A body's prefix replays in THREE situations, and a prefix event may be
    suppressed only if it is redundant in ALL of them:
      * first pass         — entering state = the previous body's exit state
                             (body 0: the leading setup Patch/Vol, bias/fill at
                             the engine's channel-reset defaults 0/0);
      * repeat iterations  — RepeatEnd(count>1) re-enters the SAME body, so the
                             entering state is the body's OWN exit state;
      * loop passes        — Jump -> LoopPoint re-enters body 0 with the exit
                             state of the FINAL body (engine channel state is
                             NOT reset at the loop seam).

    `bodies` = [(events, repeat)] as emitted (non-empty, repeat clamped);
    `recs`   = dense local FmPatch records (bank order);
    `lead_fp` = the FmPatch bytes the leading setup Patch loads.

    Returns (meta, ventry, bentry, fentry): per-body metadata dicts + the three
    per-body entry-state sets. Exit states are DETERMINISTIC wherever the body
    itself establishes the state (a VOICE fixes the voice+fill, the prefix-reset
    invariant fixes untouched opbias ops at 0); bodies that never touch a state
    pass their entry set through, so the sets are closed by fixpoint iteration.
    """
    n = len(bodies)
    ZERO_BIAS = (0, 0, 0, 0)
    meta = []
    for ev, _rep in bodies:
        first_patch = None            # the body's first voice event (a full Patch:
                                      #   the walker starts every body at prev_fp=None)
        state = None                  # running FmPatch bytes through Patch/RegDelta
        fills = []                    # NoteFill values in emission order
        bias = [0, 0, 0, 0]           # running bias from the post-prefix baseline 0
        first_load_bias = None        # bias state AT the opening Patch load
        load_bias = None              # bias state at the body's LAST patch load
        for e in ev:
            if isinstance(e, Patch):
                if first_patch is None:
                    first_patch = e
                    first_load_bias = tuple(bias)
                load_bias = tuple(bias)
                state = bytearray(recs[e.patch])
            elif isinstance(e, RegDelta):
                for rs, val in e.entries:
                    group = (rs >> REGDELTA_GROUP_SHIFT) & 0x0F
                    op = rs & REGDELTA_OP_MASK
                    state[2 + group * 4 + op] = val & 0xFF
            elif isinstance(e, NoteFill):
                fills.append(e.master)
            elif isinstance(e, OpBias):
                bias[e.op] = e.val
        meta.append({
            "first_patch": first_patch,
            "first_fp": bytes(recs[first_patch.patch]) if first_patch else None,
            "last_fp": bytes(state) if state is not None else None,
            "first_fill": fills[0] if fills else None,
            "last_fill": fills[-1] if fills else None,
            # bias at the opening load: the first note group's own OP commands
            # are flushed BEFORE the Patch, so the load can carry a nonzero bias
            # even though the body was entered clean — such a Patch is
            # LOAD-BEARING (it is what applies the bias to the modulator TLs)
            # and must never be thinned.
            "first_load_bias": first_load_bias,
            # exit values: last in-body value per state, else pass-through /
            # (for bias) the prefix-guaranteed 0 baseline. `load_bias` exit is
            # unaffected by thinning: the opening Patch is only ever dropped
            # when its load bias AND every entering load bias are 0, so the
            # effective latched value stays 0 either way.
            "bias_exit": tuple(bias),
            "load_bias_exit": load_bias,
        })

    ventry = [set() for _ in range(n)]   # entry voice FmPatch bytes
    bentry = [set() for _ in range(n)]   # entry opbias 4-tuples
    fentry = [set() for _ in range(n)]   # entry NoteFill values
    lentry = [set() for _ in range(n)]   # entry bias-at-last-patch-load tuples

    def vexit(k):
        m = meta[k]
        return {m["last_fp"]} if m["last_fp"] is not None else set(ventry[k])

    def fexit(k):
        m = meta[k]
        return {m["last_fill"]} if m["last_fill"] is not None else set(fentry[k])

    def bexit(k):
        return {meta[k]["bias_exit"]}

    def lexit(k):
        m = meta[k]
        return ({m["load_bias_exit"]} if m["load_bias_exit"] is not None
                else set(lentry[k]))

    for _round in range(4 * n + 8):      # monotone sets -> guaranteed fixpoint
        changed = False
        for k in range(n):
            v, b, f, l = set(), set(), set(), set()
            if k == 0:
                v.add(lead_fp)           # leading setup Patch (first pass)
                b.add(ZERO_BIAS)         # seq clear zeroes sc_opbias
                f.add(0)                 # channel-reset default fill = legato
                l.add(ZERO_BIAS)         # the leading Patch loads with bias 0
                v |= vexit(n - 1); b |= bexit(n - 1)                     # loop
                f |= fexit(n - 1); l |= lexit(n - 1)
            else:
                v |= vexit(k - 1); b |= bexit(k - 1)
                f |= fexit(k - 1); l |= lexit(k - 1)
            if bodies[k][1] > 1:         # repeat iterations re-enter the body
                v |= vexit(k); b |= bexit(k); f |= fexit(k); l |= lexit(k)
            if ((v - ventry[k]) or (b - bentry[k]) or (f - fentry[k])
                    or (l - lentry[k])):
                changed = True
                ventry[k] |= v; bentry[k] |= b
                fentry[k] |= f; lentry[k] |= l
        if not changed:
            break
    else:
        raise RuntimeError("body entry-state analysis did not converge")
    return meta, ventry, bentry, fentry, lentry


def _thin_body_prefixes(bodies, recs, lead_fp, stats):
    """Suppress the redundant per-body state-reset prefix (the micro-pause fix).

    The naive emission made EVERY body boundary reload the full state on all
    channels in one sequencer tick — OpBias(0)x4 + a full ~26-write Patch (the
    walker's self-contained prev_fp=None) + a NoteFill — ~226 chip writes at
    the worst boundary (the audible pre-measure-5 stall). Almost all of it is
    redundant: the state entering the body already matches. Using the entry-state
    sets from _analyze_body_entry_states:

      * OpBias(op, 0) reset: emitted ONLY for ops where some entering scenario
        holds a nonzero bias (most bodies never touch OpBias -> no resets).
      * Patch: the opening full Patch is thinned by the normal minimal-delta
        rule (_voice_step_event: identical voice -> dropped, small delta ->
        RegDelta, else kept) ONLY when the load is provably a no-op for the
        chip in every scenario. The engine latches MEV_OPBIAS and applies it to
        the modulator TLs only at patch load (Fm_PatchTlGroup), so the Patch
        must stay whenever it is the load that carries a bias:
          - a prefix bias reset is emitted (the reload pushes the cleared TLs),
          - the body's own first note group sets a bias before the Patch
            (first_load_bias != 0 — the load applies it),
          - some entering scenario's LAST patch load latched a nonzero bias
            (the resident modulator TLs differ from the raw voice bytes),
          - or the entering voice is scenario-dependent / a genuine change.
      * NoteFill: dropped when every entering scenario already holds the body's
        opening fill (it persists in the engine).

    In-body events after the opening voice are untouched: the opening voice's
    post-state is the SAME first_fp in every scenario (loaded, delta'd to, or
    already resident), so the walker's in-body minimal-delta chain stays valid.

    Mutates the body event lists + `stats` in place; returns the per-body
    OpBias-reset op lists for emission.
    """
    ZERO_BIAS = (0, 0, 0, 0)
    meta, ventry, bentry, fentry, lentry = _analyze_body_entry_states(
        bodies, recs, lead_fp)
    reset_plans = []
    for k, (ev, _rep) in enumerate(bodies):
        m = meta[k]
        reset_ops = sorted({i for bias in bentry[k] for i in range(4)
                            if bias[i] != 0})
        reset_plans.append(reset_ops)
        # NoteFill: the body's FIRST NoteFill is the opening voice's gate
        # re-emission (cur_fill=None); drop it when already resident.
        if (m["first_fill"] is not None and len(fentry[k]) == 1
                and next(iter(fentry[k])) == m["first_fill"]):
            for i, e in enumerate(ev):
                if isinstance(e, NoteFill):
                    del ev[i]
                    stats["notefill"] -= 1
                    break
        # Patch: thin the opening full Patch by the minimal-delta rule, unless
        # it is bias-load-bearing (see docstring) or the entering voice is
        # scenario-dependent.
        if (m["first_patch"] is None or reset_ops or len(ventry[k]) != 1
                or m["first_load_bias"] != ZERO_BIAS
                or lentry[k] != {ZERO_BIAS}):
            continue
        entry_fp = next(iter(ventry[k]))
        step, kind = _voice_step_event(entry_fp, m["first_fp"],
                                       m["first_patch"].patch)
        if kind == "patch":
            continue                     # full reload genuinely needed
        idx = ev.index(m["first_patch"])
        stats["patch"] -= 1
        if kind == "none":
            del ev[idx]                  # voice already resident
        else:
            ev[idx] = step               # small delta covers every scenario
            stats["regdelta"] += 1
    return reset_plans


def build_native_songdesc(rom, pitchtable_offset=0,
                          suppress_redundant_state=True):
    """Translate Moving Trucks (real song data) into a packer SongDesc + return the
    per-channel opcode stats and the patch bank info.

    Returns (song, stats, (bank_bytes, remap, pcount)).
    pitchtable_offset: BE offset (relative to the song header) of the per-song
    pitch table within the streaming block; 0 = engine-default table.
    suppress_redundant_state: thin the per-body state-reset prefixes to the
    events that actually change state (_thin_body_prefixes). False = emit the
    naive self-contained prefixes (kept for the equivalence regression test).
    """
    bank = _load_voice_bank(rom)
    channels_data = parse_song(rom)
    bank_bytes, remap, pcount = build_native_patch_bank(rom, channels_data, bank)

    stats_all = []
    channels = []
    for ci, block in enumerate(channels_data):
        if ci >= len(NATIVE_FM_ROUTES):
            break
        route = NATIVE_FM_ROUTES[ci]
        stats = {"pitchenv": 0, "regdelta": 0, "patch": 0, "pan": 0,
                 "opbias": 0, "rest": 0, "vol_dropped": 0, "glide_emitted": 0,
                 "notefill": 0}
        walker = _Walker(rom, bank, remap, stats)
        # per-channel re-key window (the cadence-coalescing floor) — see
        # REKEY_WINDOW_TICKS: port-0/even-frame channels (ch0-3) re-key at ~3 ticks,
        # odd-frame channels (ch4-5) at ~2 ticks (the closest integer to the oracle's
        # measured 1.5-tick / ~87 ms re-attack).
        walker.rekey_window = (REKEY_WINDOW_TICKS[ci]
                               if ci < len(REKEY_WINDOW_TICKS) else 3)
        # #4 GATE ARTICULATION: this source channel's { voice -> NoteFill frames }
        # map (extracted from mt_ref.vgm — see NATIVE_GATE_TABLES). The walker
        # emits NoteFill(n)/NoteFill(0) at voice changes where the gate changes.
        walker.gate_table = (NATIVE_GATE_TABLES[ci]
                             if ci < len(NATIVE_GATE_TABLES) else {})
        # No octave correction for the correct song (Bank2 song4): its PITCH points
        # already render to the oracle's per-channel block band. octave_cap=None ->
        # octave_cap_idx is an identity pass-through (see OCTAVE CORRECTION above).
        walker.octave_cap = _OCTAVE_CAP_DEFAULT
        # The channel's FIRST voice -> the leading-setup Patch (below). The walker
        # itself stays self-contained (every body opens with a full Patch computed
        # vs prev_fp=None); redundant opening loads are then thinned by the
        # loop-aware analysis (_thin_body_prefixes), which proves per body that
        # the entering voice is the same on the first pass, on every repeat
        # iteration AND across the LoopPoint..Jump seam before dropping one.
        first_vi = _channel_first_voice(rom, block)
        if first_vi is not None:
            walker.first_local = remap[first_vi]

        # --- translate every pattern body (each body self-contained; empty bodies
        # dropped here so the prefix analysis sees exactly the emitted chain). ---
        bodies = []
        tempo_base = MT_FORMAT_CODE
        for entry in block["entries"]:
            # per-pattern tempo override (non-zero replaces the base). MT only sets
            # it on entry 0 (= the song format code); recorded for completeness.
            if entry["tempo"] != 0:
                tempo_base = entry["tempo"]
            walker.tempo_base = tempo_base    # glide_frames -> ticks pacing
            body = walker.walk_body(seq_addr(rom, entry["seq"]),
                                    entry["transpose"])
            if body:
                bodies.append((body, max(1, min(255, entry["repeat"]))))

        # --- per-body prefix thinning (the boundary micro-pause fix): the naive
        # emission made EVERY body boundary reload OpBias(0)x4 + a full ~26-write
        # Patch + NoteFill on all six channels in ONE sequencer tick (~226 chip
        # writes at the worst boundary = the audible 25-42 ms stall before
        # measure 5). ChannelReset parity ($044F clears op_mod every pattern
        # boundary — e.g. seq123 leaves OP1-4=$0F biased and the following bass
        # seq114 only resets OP2) is PRESERVED: a reset is emitted exactly where
        # some entering scenario still holds a nonzero bias, and it then forces
        # the full Patch so the cleared modulator TLs reach the chip (MEV_OPBIAS
        # only latches; Fm_PatchTlGroup applies it at patch load). ---
        recs = [bank_bytes[i * FMPATCH_LEN:(i + 1) * FMPATCH_LEN]
                for i in range(pcount)]
        lead_local = walker.first_voice_local() if remap else 0
        if suppress_redundant_state and recs and bodies:
            reset_plans = _thin_body_prefixes(bodies, recs,
                                              bytes(recs[lead_local]), stats)
        else:
            reset_plans = [[0, 1, 2, 3]] * len(bodies)

        # --- leading setup: Patch(first voice) + Vol so the packer accepts the FM
        # channel (the guard wants Patch+Vol before the first keyed note); it also
        # anchors the prefix analysis: body 0's first-pass entering voice IS this
        # Patch, so the body's (identical) opening reload is provably redundant. ---
        # Full volume (no carrier attenuation): Moving Trucks emits no source VOL
        # commands, so the driver default is max. A lower fixed Vol (was 110) adds
        # LogVolumeLut attenuation to the carriers (110 -> +4) and saps the kick's
        # punch; the oracle's carriers sit at base TL with dynamics from voice-steps.
        events = [Patch(lead_local), Vol(127)]
        # (Gate articulation is emitted per voice-change inside the bodies — see
        # NATIVE_GATE_TABLES / _Walker._voice. No blanket per-channel NoteFill here:
        # the old FM6-wide fill leaked onto its held melodic stabs and truncated
        # them; the engine's channel-reset default fill of 0 (legato) is correct
        # until the first VOICE command picks its gate.)
        events.append(LoopPoint())
        for (body, repeat), reset_ops in zip(bodies, reset_plans):
            events.append(RepeatStart())
            # OpBias resets stay INSIDE the RepeatStart so a repeat iteration
            # re-clears its own leftovers, exactly like ChannelReset.
            events.extend(OpBias(op, 0) for op in reset_ops)
            events.extend(body)
            events.append(RepeatEnd(repeat))
        events.append(Jump())

        channels.append(ChannelDesc(route, events))
        stats["porta_dropped"] = walker.porta_dropped
        stats["route"] = route
        stats["tempo_base"] = tempo_base
        stats_all.append(stats)

    # Global hardware LFO: assert $22=$08 (enable, rate 0 ~3.8 Hz) at song
    # start, as the B&R reference does. SndDrv_Init already enables this at
    # boot, so on a cold start it's a no-op — the event exists so MT's LFO
    # state is per-song deterministic: a previously played song's MEV_LFO
    # (any authored rate/disable) must not leak into this one. Per-channel
    # depth rides the voices' $B4 FMS bits (Pan/patch path).
    # Rides channel 0's stream, before its LoopPoint (fires once).
    channels[0].events.insert(0, Lfo(0x08))

    # FM6=FM (DAC off) + stream from ROM. The legacy header tempo byte keeps the
    # song format code ($38) for visibility; the OPERATIVE header tempo_mod is
    # the S3K-model conversion of that base (56 -> mod 183; see
    # zyrinx_base_to_tempo_mod for the -0.196% rounding note).
    song = SongDesc(tempo=MT_FORMAT_CODE,
                    tempo_mod=zyrinx_base_to_tempo_mod(MT_FORMAT_CODE),
                    channels=channels, flags=SH_F_FM6_FM | SH_F_STREAM)
    song.pitchtable_offset = pitchtable_offset   # carried into pack_song below
    return song, stats_all, (bank_bytes, remap, pcount)


# ----------------------------------------------------------------------------
# Boundary-burst metric — per-tick chip-write cost of the packed event stream
# ----------------------------------------------------------------------------
# Root cause of the audible pre-measure-5 micro-pause: every pattern-body
# boundary made ALL SIX channels process their state-reset prefix in ONE
# sequencer tick (~226 chip writes at the worst boundary), overrunning the
# 16.7 ms frame by 25-42 ms so every channel's next note keyed late. These
# helpers replay the SongDesc event streams on the shared event-tick clock and
# tally the write cost per tick, so the burst profile is a data-level
# regression check (no emulator needed).

# Approximate chip-write cost per zero-tick event (a full FmPatch load writes
# ~26 YM registers; OpBias/Vol are cheap latches counted at the instrumented
# weight; NoteFill is engine-state only).
_BURST_WRITE_COST = {
    Patch: 26, Vol: 2, OpBias: 2, Pan: 1, Lfo: 1, NoteFill: 0,
}
_BURST_KEYON_COST = 4        # key-off + A4/A0 + key-on


def expand_channel_stream(events, loops=2):
    """Flatten one channel's packed event stream the way the engine plays it:
    RepeatStart..RepeatEnd(n) bodies replayed n times, then `loops` passes of
    the LoopPoint..Jump segment appended (pass 1 plays start..Jump). Control
    markers are dropped; the result is a linear event list."""
    lp = next((i for i, e in enumerate(events) if isinstance(e, LoopPoint)),
              len(events))
    jp = next((i for i, e in enumerate(events) if isinstance(e, Jump)),
              len(events))

    def expand(seq):
        out = []
        stack = []
        for e in seq:
            if isinstance(e, RepeatStart):
                stack.append(len(out))
            elif isinstance(e, RepeatEnd):
                start = stack.pop()
                body = out[start:]               # inner repeats already expanded
                for _ in range(e.count - 1):
                    out.extend(body)
            elif isinstance(e, (LoopPoint, Jump)):
                pass
            else:
                out.append(e)
        return out

    stream = expand(events[:lp])
    loop_seg = expand(events[lp:jp])
    for _ in range(max(1, loops)):
        stream.extend(loop_seg)
    return stream


def simulate_write_bursts(song, loops=2):
    """Tally the per-event-tick chip-write cost of a SongDesc across all
    channels (repeats expanded, `loops` loop passes). Returns {tick: writes}.
    All MT channels share one global tick clock (the tempo is global), so tick
    indices align across channels and a body boundary shows up as one spike."""
    cost = {}
    for chan in song.channels:
        t = 0
        cur = 0
        for e in expand_channel_stream(chan.events, loops=loops):
            if isinstance(e, SetDur):
                cur = e.ticks
            elif isinstance(e, (PitchEnv, Note)):
                cost[t] = cost.get(t, 0) + _BURST_KEYON_COST
                t += cur
            elif isinstance(e, (NoteDur, NoteRaw)):
                cost[t] = cost.get(t, 0) + _BURST_KEYON_COST
                t += e.dur
            elif isinstance(e, Rest):
                t += cur
            else:
                w = _BURST_WRITE_COST.get(type(e))
                if w is None:
                    w = len(e.entries) if isinstance(e, RegDelta) else 0
                if w:
                    cost[t] = cost.get(t, 0) + w
    return cost


def emit_native_song(rom=None, song_out=None, patches_out=None,
                     pitchtab_out=None, song_label="Song_MovingTrucks",
                     patch_label="MovingTrucks_Patches",
                     pitchtab_label="MovingTrucks_PitchTable_Stream",
                     emit_bin=False):
    """Generate the three native Moving Trucks data files (song / patch bank /
    streaming pitch table) and return a report dict.

    The streaming block layout (one bank-aligned 32KB bank, set up in main.asm)
    is [song][pitch table][patch bank], contiguous. The song header's
    pitchtable_ptr is the BE offset of the pitch table = len(packed song); the
    loader resolves it to an absolute window ptr (base + offset). The patch bank
    ptr is wired separately via SongPatchTable (its own window ptr).

    emit_bin=True additionally writes the .bin sibling of each .asm output
    (bin_path_for: same stem, .bin extension) with the exact payload bytes the
    .asm's dc.b lines encode — no labels, no align padding.
    """
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.normpath(os.path.join(here, ".."))
    if rom is None:
        rom = open(ROM_PATH, "rb").read()
    if song_out is None:
        song_out = os.path.join(root, "games", "sonic4", "data", "sound", "song_movingtrucks.asm")
    if patches_out is None:
        patches_out = os.path.join(root, "games", "sonic4", "data", "sound",
                                   "movingtrucks_patches.asm")
    if pitchtab_out is None:
        pitchtab_out = os.path.join(root, "games", "sonic4", "data", "sound",
                                    "movingtrucks_pitchtable_stream.asm")

    # First pass: pack with pitchtable_ptr=0 to learn the packed song length (=
    # the pitch table's offset, since it is placed immediately after the song).
    song0, _, _ = build_native_songdesc(rom, pitchtable_offset=0)
    song_len = len(pack_song(song0))

    # Second pass: pack with the real pitch-table offset embedded in the header.
    song, stats_all, (bank_bytes, remap, pcount) = build_native_songdesc(
        rom, pitchtable_offset=song_len)
    blob = pack_song(song, pitchtable_offset=song_len)

    # --- write the song .asm (with the real pitchtable_ptr in the header) ---
    _write_blob_asm(blob, song_label, song_out)
    if emit_bin:
        song_bin = bin_path_for(song_out)
        with open(song_bin, "wb") as f:
            f.write(blob)

    # --- write the per-song FmPatch bank (reuse zyrinx_port's emitter) ---
    with open(patches_out, "w") as f:
        f.write(emit_patch_bank_asm(bank_bytes, remap, pcount, patch_label))
    if emit_bin:
        patches_bin = bin_path_for(patches_out)
        with open(patches_bin, "wb") as f:
            f.write(bank_bytes)

    # --- write the streaming-block copy of the 132-entry pitch table (distinct
    # label so it doesn't collide with the engine-default inline copy; dc.b since
    # it lives in the 68k ROM data area, not the Z80 phase-0 blob). ---
    write_pitchtable_asm(pitchtab_out, label=pitchtab_label, directive="dc.b")
    if emit_bin:
        write_pitchtable_bin(bin_path_for(pitchtab_out))

    return {
        "song_bytes": len(blob),
        "song_label": song_label,
        "patch_count": pcount,
        "patch_bytes": len(bank_bytes),
        "pitchtable_bytes": 2 * PITCHTAB_COUNT,
        "pitchtable_offset": song_len,
        "channels": stats_all,
        "song_out": song_out,
        "patches_out": patches_out,
        "pitchtab_out": pitchtab_out,
    }


def _write_blob_asm(blob, label, out_path, offset_symbol="MT_PITCHTAB_OFFSET"):
    """Emit a packed song blob as a labeled dc.b block (same shape as
    song_packer.emit_asm, but for a blob already packed with a pitchtable_ptr)."""
    lines = []
    lines.append("; " + "=" * 70)
    lines.append("; %s.asm — GENERATED by tools/zyrinx_player.py "
                 "(emit_native_song) — DO NOT EDIT BY HAND." % label)
    lines.append("; Native port of B&R \"Moving Trucks\" (Zyrinx Bank2 song4 @ $1F0BDF,")
    lines.append("; real song data — NOT a register replay). Regenerate:")
    lines.append(";   python3 tools/zyrinx_player.py --emit-native-song")
    lines.append("; Stream pointers in the header are 16-bit BE offsets relative to")
    lines.append("; the %s label (loader adds the base). FM6=FM, streamed." % label)
    lines.append("; " + "=" * 70)
    lines.append("")
    lines.append("%s:" % label)
    for i in range(0, len(blob), 16):
        chunk = blob[i:i + 16]
        lines.append("    dc.b   " + ", ".join("$%02X" % b for b in chunk))
    lines.append("%s_End:" % label)
    lines.append("")
    lines.append("; NO align here — the pitch table MUST follow CONTIGUOUSLY: the song")
    lines.append("; header bakes its offset as the unpadded song length, so a single pad")
    lines.append("; byte shifts every pitch lookup one byte early (= the whole song plays")
    lines.append("; a semitone flat; shipped bug, root-caused 2026-07-01). main.asm")
    lines.append("; asserts the layout against this constant at build time:")
    lines.append("%s equ $%04X    ; = packed song length (header pitchtable_ptr)"
                 % (offset_symbol, len(blob)))
    with open(out_path, "w") as f:
        f.write("\n".join(lines))
        f.write("\n")


# ----------------------------------------------------------------------------
# VGM rendering
# ----------------------------------------------------------------------------
def render_vgm(channels, path, duration_s):
    """Render the event log into a minimal YM2612 VGM.

    Writes A4/A0 + key-on/off for each event at its time. Uses a fixed FM patch
    so the file is audible; pitch/key timing is what matters for validation.
    """
    # Merge all events sorted by time.
    events = []
    for chan in channels:
        events.extend(chan.events)
    events.sort(key=lambda e: (e["time_s"]))

    body = bytearray()

    def ym0(reg, val):
        body.append(0x52)
        body.append(reg & 0xFF)
        body.append(val & 0xFF)

    def ym1(reg, val):
        body.append(0x53)
        body.append(reg & 0xFF)
        body.append(val & 0xFF)

    def wait(samples):
        while samples > 0:
            w = min(samples, 65535)
            body.append(0x61)
            body.append(w & 0xFF)
            body.append((w >> 8) & 0xFF)
            samples -= w

    # YM channel -> (port, reg-channel-offset, key-sel)
    # ch0-2: port0 offset 0-2, keysel 0-2. ch3-5: port1 offset 0-2, keysel 4-6.
    def ch_route(ymch):
        if ymch < 3:
            return 0, ymch, ymch
        return 1, ymch - 3, (ymch - 3) + 4

    # --- init: set up a simple audible FM patch on all 6 channels ---
    # A bright-ish 2-op-feel patch (algorithm 4) so notes are clearly audible.
    def init_channel(ymch):
        port, off, ksel = ch_route(ymch)
        w = ym0 if port == 0 else ym1
        # $B0 feedback/algorithm: algorithm 4, feedback 3
        w(0xB0 + off, (3 << 3) | 4)
        # $B4 pan = both, no AMS/FMS
        w(0xB4 + off, 0xC0)
        # operators: regs step +4 for the 4 operators of this channel
        for opo in range(4):
            r = off + opo * 4
            w(0x30 + r, 0x01)   # DT/MUL
            # TL: carriers loud, modulators moderate (alg4: op1/op3 carriers-ish)
            w(0x40 + r, 0x18 if opo in (1, 3) else 0x28)
            w(0x50 + r, 0x1F)   # RS/AR  fast attack
            w(0x60 + r, 0x08)   # AM/D1R
            w(0x70 + r, 0x04)   # D2R
            w(0x80 + r, 0x1F)   # SL/RR
    ym0(0x22, 0x00)  # LFO off
    ym0(0x27, 0x00)  # timers off
    ym0(0x2B, 0x00)  # DAC off
    for ymch in range(6):
        init_channel(ymch)

    cur_sample = 0
    for e in events:
        tgt = int(round(e["time_s"] * VGM_SR))
        if tgt > cur_sample:
            wait(tgt - cur_sample)
            cur_sample = tgt
        ymch = e["ym_channel"]
        port, off, ksel = ch_route(ymch)
        w = ym0 if port == 0 else ym1
        if e["event"] == "on":
            # key off first (re-articulate), set freq, key on
            ym0(0x28, ksel)               # key off
            w(0xA4 + off, e["a4"])
            w(0xA0 + off, e["a0"])
            # pan
            w(0xB4 + off, e["pan"] if e["pan"] else 0xC0)
            ym0(0x28, 0xF0 | ksel)        # key on all ops
        else:
            ym0(0x28, ksel)               # key off

    # tail
    end_sample = int(round(duration_s * VGM_SR))
    if end_sample > cur_sample:
        wait(end_sample - cur_sample)
    body.append(0x66)  # end

    # --- header ---
    header = bytearray(0x40)
    header[0:4] = b"Vgm "
    struct.pack_into("<I", header, 0x08, 0x150)            # version 1.50
    struct.pack_into("<I", header, 0x2C, YM_CLOCK)         # YM2612 clock
    struct.pack_into("<I", header, 0x18, end_sample)       # total samples
    struct.pack_into("<I", header, 0x34, 0x40 - 0x34)      # data offset (rel) -> 0x40
    eof = 0x40 + len(body)
    struct.pack_into("<I", header, 0x04, eof - 0x04)       # EOF offset
    with open(path, "wb") as f:
        f.write(header)
        f.write(body)
    return len(events)


def main():
    # --emit-pitchtable: dump the 132-entry pitch table to the game sound data
    # dir as the banked .emp head (no ROM needed — the table is the hardcoded
    # §2.4 dump). sigil lowers movingtrucks_pitchtable.emp to the BINCLUDE'd
    # movingtrucks_pitchtable.bin (seam2::emit_pitchtable); the old .asm twin is
    # deleted (flip Stage-0).
    if "--emit-pitchtable" in sys.argv:
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        out = os.path.normpath(os.path.join(
            here, "..", "games", "sonic4", "data", "sound", "movingtrucks_pitchtable.emp"))
        write_pitchtable_emp(out)
        print("wrote", out)
        return

    # --emit-native-song (Task 8): walk the REAL Moving Trucks song data and emit
    # the native packed song + per-song FmPatch bank + streaming pitch table.
    if "--emit-native-song" in sys.argv:
        rep = emit_native_song(emit_bin="--emit-bin" in sys.argv)
        print("wrote", rep["song_out"], "(%d bytes)" % rep["song_bytes"])
        print("wrote", rep["patches_out"],
              "(%d FmPatch records, %d bytes)"
              % (rep["patch_count"], rep["patch_bytes"]))
        print("wrote", rep["pitchtab_out"],
              "(%d bytes, offset %d)"
              % (rep["pitchtable_bytes"], rep["pitchtable_offset"]))
        total = (rep["song_bytes"] + rep["pitchtable_bytes"]
                 + rep["patch_bytes"])
        print("streaming block total: %d bytes (fits one 32KB bank: %s)"
              % (total, "YES" if total <= 0x8000 else "NO"))
        for ci, st in enumerate(rep["channels"]):
            print("  ch%d -> route %d: PITCHENV=%d REGDELTA=%d PATCH=%d "
                  "PAN=%d OPBIAS=%d REST=%d NOTEFILL=%d "
                  "(glides=%d vol_dropped=%d porta=%d)"
                  % (ci, st["route"], st["pitchenv"], st["regdelta"],
                     st["patch"], st["pan"], st["opbias"], st["rest"],
                     st.get("notefill", 0), st.get("glide_emitted", 0),
                     st["vol_dropped"], st["porta_dropped"]))
        return

    glide_as_vol = "--vol" in sys.argv
    duration_s = 159.0
    rom = open(ROM_PATH, "rb").read()
    channels = simulate(rom, duration_s, glide_as_vol=glide_as_vol)

    nev = render_vgm(channels, "/tmp/mt_player.vgm", duration_s)

    # event dump
    dump = {
        "song": "Moving Trucks (B&R, Bank2 song4 @ $1F0BDF)",
        "frame_rate_hz": FODD,
        "duration_s": duration_s,
        "interpretation_0A_12": "vol" if glide_as_vol else "portamento",
        "channels": [],
    }
    for chan in channels:
        dump["channels"].append({
            "driver_channel": chan.ch,
            "ym_channel": chan.ch,
            "active": chan.active,
            "n_events": len(chan.events),
            "events": chan.events,
        })
    with open("/tmp/mt_player_events.json", "w") as f:
        json.dump(dump, f, indent=1)

    print(f"Rendered VGM: /tmp/mt_player.vgm ({nev} note events)")
    print(f"Event dump:   /tmp/mt_player_events.json")
    for chan in channels:
        ons = [e for e in chan.events if e["event"] == "on"]
        print(f"  ch{chan.ch}: {len(chan.events)} events, {len(ons)} key-ons, active={chan.active}")


if __name__ == "__main__":
    main()
