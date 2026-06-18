#!/usr/bin/env python3
"""
Zyrinx "Advanced Z80 Player" REFERENCE PLAYER (The Adventures of Batman & Robin).

Simulates the reverse-engineered Zyrinx sound driver playing song 3
("Moving Trucks", Bank 1) frame-by-frame and produces:
  (a) a rendered VGM  (/tmp/mt_player.vgm)         -- YM2612 register writes with timing
  (b) a per-channel musical-event dump (/tmp/mt_player_events.json) for engine porting

Authoritative spec: /tmp/zyrinx_re_{commands,timing_pitch,layout,modulation}.md

The driver model (verified against the driver binary, see comments):
  * Song body = 6 consecutive per-channel blocks: [count][loopback][count x 4-byte entries].
  * Pattern entry = [seq_index, transpose(signed), repeat, tempo].
  * Sequences resolved through the bank-shared seq pointer table @ ROM $1E91E3.
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
SEQ_PTR_TABLE = 0x1E91E3      # 154 x 3-byte [bank, z80_hi, z80_lo]
SONG3_ADDR = 0x1E886F         # Moving Trucks song body (404 bytes)
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
    """Return (A4[], A0[], block[], fnum[]) indexed 0..0x83, plus a reverse (block,fnum)->idx."""
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
# Command operand sizes / classification for the two-table dispatch
# ----------------------------------------------------------------------------
# Table-1 (first command of a tick group):
#   $00-$08 PITCH_n  -> (op//2 + 1) note operands
#   $0A-$12 VOL/GLIDE-> (op-0x0A)//2 + 1 level operands + 1 duration byte
#   $14 PARAM 1, $16 NOP 0, $18 VOICE 1, $1A GATE 0, $1C LOOP 0, $1E NOP 0
#   $20-$2E CH-select 0, $30-$36 PAN 0, $38-$3E OP 1, $40+ NOP 0
# Table-2 differs: $00-$08 = NOTE trigger (0 operand, ends group);
#   $1C = reset-only; $1E = channel-off.


def parse_song(rom):
    """Parse song 3 into 6 channel blocks of pattern entries."""
    p = SONG3_ADDR
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
    glide_as_vol = "--vol" in sys.argv
    duration_s = 159.0
    rom = open(ROM_PATH, "rb").read()
    channels = simulate(rom, duration_s, glide_as_vol=glide_as_vol)

    nev = render_vgm(channels, "/tmp/mt_player.vgm", duration_s)

    # event dump
    dump = {
        "song": "Moving Trucks (B&R, Bank1 song3)",
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
