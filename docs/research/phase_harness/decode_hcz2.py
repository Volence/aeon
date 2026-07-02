#!/usr/bin/env python3
"""Decode the packed HCZ2 song blob (song_hcz2.asm) per the v0 format.
Walk each channel stream, sum event-ticks, note terminator + loop point."""
import re, sys

ASM = "/home/volence/sonic_hacks/aeon/.worktrees/sound-perf-budget/games/sonic4/data/sound/song_hcz2.asm"

data = bytearray()
for line in open(ASM):
    m = re.match(r"\s*dc\.b\s+(.*)", line)
    if not m:
        continue
    for tok in m.group(1).split(','):
        tok = tok.strip()
        if tok.startswith('$'):
            data.append(int(tok[1:], 16))
        elif tok:
            data.append(int(tok, 0))

print(f"blob size: {len(data)} (${len(data):04X})")

flags, tempo, tempo_base, n = data[0], data[1], data[2], data[3]
pt = (data[4] << 8) | data[5]
print(f"flags=${flags:02X} tempo=${tempo:02X} tempo_base={tempo_base} channels={n} pitchtable_ptr=${pt:04X}")
chans = []
off = 6
for i in range(n):
    route = data[off]
    cmd = (data[off+1] << 8) | data[off+2]
    mod = (data[off+3] << 8) | data[off+4]
    chans.append((route, cmd, mod))
    off += 5
patch_ptr = (data[off] << 8) | data[off+1]
print(f"patch_table_ptr=${patch_ptr:04X}")

# opcode -> operand byte count (fixed ones)
FIXED = {0xE0:1, 0xE1:1, 0xE2:1, 0xE3:2, 0xE4:1, 0xE5:0, 0xE6:1, 0xE7:3,
         0xE9:2, 0xEB:1, 0xEC:4, 0xED:1, 0xEE:0, 0xEF:0, 0xF0:0, 0xF1:0,
         0xF2:1, 0xF3:1, 0xF4:1, 0xF6:1, 0xF7:1, 0xF8:3, 0xF9:2, 0xFF:0}

FPS = 59.92
TEMPO_CUR = 16.0  # SND_TEMPO_CUR default (100% speed)
frames_per_tick = tempo_base / TEMPO_CUR

for ci, (route, cmd, mod) in enumerate(chans):
    p = cmd
    dur_default = 0
    ticks = 0
    loop_pt = None          # offset saved by MEV_LOOP_POINT
    ticks_at_loop = 0
    end = None
    repeats = []            # (body_start, remaining) simple emulation
    rpt_start = None
    rpt_count = 0
    events = 0
    last_time_ev_off = None
    safety = 2_000_000
    while p < len(data) and safety:
        safety -= 1
        op = data[p]; p0 = p; p += 1
        events += 1
        if op < 0x80:
            dur_default = op
        elif op == 0x80:
            ticks += dur_default
            last_time_ev_off = p0
        elif op <= 0xDF:
            ticks += dur_default
            last_time_ev_off = p0
        elif op == 0xE3:
            p += 1
            ticks += data[p]; p += 1
            last_time_ev_off = p0
        elif op == 0xE7:
            p += 2
            ticks += data[p]; p += 1
            last_time_ev_off = p0
        elif op == 0xE8:  # PITCHENV: count then count idx bytes; default duration
            cnt = data[p]; p += 1 + cnt
            ticks += dur_default
            last_time_ev_off = p0
        elif op == 0xEA:  # REGDELTA: count then 2*count
            cnt = data[p]; p += 1 + 2*cnt
        elif op == 0xE5:  # REPEAT_START
            rpt_start = p
        elif op == 0xE6:  # REPEAT_END nn
            nn = data[p]; p += 1
            if rpt_count == 0:
                rpt_count = nn
            rpt_count -= 1
            if rpt_count > 0:
                p = rpt_start
        elif op == 0xEE:
            loop_pt = p
            ticks_at_loop = ticks
        elif op == 0xEF:
            end = ('JUMP', p0, loop_pt)
            break
        elif op == 0xFF:
            end = ('END', p0, None)
            break
        else:
            oplen = FIXED.get(op)
            if oplen is None:
                end = ('BADOP', p0, op)
                break
            p += oplen
    secs = ticks * frames_per_tick / FPS
    loop_secs = (ticks - ticks_at_loop) * frames_per_tick / FPS
    print(f"ch{ci} route=${route:02X} cmd=${cmd:04X} mod=${mod:04X} "
          f"ticks={ticks} = {secs:7.2f}s  loop_pt={'$%04X' % loop_pt if loop_pt is not None else 'NONE'} "
          f"body={loop_secs:6.2f}s  end={end} events={events}")
