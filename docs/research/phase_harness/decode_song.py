#!/usr/bin/env python3
"""Decode a packed music-format-v0 blob (.asm dc.b) and report per-channel
tick lengths, terminators, loop-point positions, loop-body lengths."""
import re, sys

def load_blob(path):
    data = []
    for line in open(path):
        line = line.strip()
        if line.startswith("dc.b"):
            for tok in line[4:].split(","):
                tok = tok.strip()
                if tok.startswith("$"):
                    data.append(int(tok[1:], 16))
    return bytes(data)

ROUTES = {0:"FM1",1:"FM2",2:"FM3",3:"FM4",4:"FM5",5:"FM6",
          6:"PSG1",7:"PSG2",8:"PSG3",9:"PSGN",10:"DAC"}

# opcode -> operand byte count (zero-tick unless noted)
OPERANDS = {
    0xE0:1, 0xE1:1, 0xE2:1, 0xE4:1, 0xE5:0, 0xE6:1,
    0xE9:2, 0xEB:1, 0xEC:4, 0xED:1, 0xEE:0, 0xEF:0,
    0xF2:1, 0xF3:1, 0xF4:1, 0xF6:1, 0xF7:1, 0xF8:3, 0xF9:2,
}

def walk(blob, off, max_steps=2_000_000):
    ticks = 0
    dur = 0
    pos = off
    loop_tick = None      # tick count when LOOP_POINT executed
    loop_pos = None
    events = 0
    rep_stack = []        # (body_start_pos, remaining or None-not-yet-seen)
    notes = 0
    terminator = None
    time_advancing_since_loop = 0
    while events < max_steps:
        events += 1
        op = blob[pos]; pos += 1
        if op <= 0x7F:                      # SetDur
            dur = op
        elif op == 0x80:                    # Rest
            ticks += dur
            if loop_tick is not None: time_advancing_since_loop += dur
        elif op <= 0xDF:                    # Note
            ticks += dur; notes += 1
            if loop_tick is not None: time_advancing_since_loop += dur
        elif op == 0xE3:                    # NoteDur pitch dd
            d = blob[pos+1]; pos += 2
            ticks += d; notes += 1
            if loop_tick is not None: time_advancing_since_loop += d
        elif op == 0xE7:                    # NoteRaw a4 a0 dd
            d = blob[pos+2]; pos += 3
            ticks += d; notes += 1
            if loop_tick is not None: time_advancing_since_loop += d
        elif op == 0xE8:                    # PitchEnv count + pts (advances default dur)
            cnt = blob[pos]; pos += 1 + cnt
            ticks += dur; notes += 1
            if loop_tick is not None: time_advancing_since_loop += dur
        elif op == 0xEA:                    # RegDelta count + 2*count
            cnt = blob[pos]; pos += 1 + 2*cnt
        elif op == 0xE5:                    # RepeatStart
            rep_stack.append([pos, None])
        elif op == 0xE6:                    # RepeatEnd nn
            nn = blob[pos]; pos += 1
            if not rep_stack:
                # matches engine: repeat with no start -> treat body as from off? bail
                terminator = "BAD_REPEAT"; break
            top = rep_stack[-1]
            if top[1] is None:
                top[1] = nn - 1
            if top[1] > 0:
                top[1] -= 1
                pos = top[0]
            else:
                rep_stack.pop()
        elif op == 0xEE:                    # LoopPoint
            loop_tick = ticks; loop_pos = pos
        elif op == 0xEF:                    # Jump
            terminator = "JUMP"; break
        elif op == 0xFF:
            terminator = "END"; break
        elif op in OPERANDS:
            pos += OPERANDS[op]
        else:
            terminator = "BADOP_%02X" % op; break
    else:
        terminator = "MAXSTEPS"
    return dict(ticks=ticks, terminator=terminator, loop_tick=loop_tick,
                loop_pos=loop_pos, notes=notes, end_pos=pos,
                loop_body_ticks=(ticks - loop_tick) if loop_tick is not None else None)

def main(path):
    blob = load_blob(path)
    print("blob size:", len(blob))
    flags, tempo, tempo_base, n = blob[0], blob[1], blob[2], blob[3]
    pitch_ptr = (blob[4] << 8) | blob[5]
    print(f"flags=${flags:02X} tempo=${tempo:02X} tempo_base={tempo_base} channels={n} pitch_ptr={pitch_ptr:#x}")
    chans = []
    p = 6
    for i in range(n):
        route = blob[p]
        cmd = (blob[p+1] << 8) | blob[p+2]
        mod = (blob[p+3] << 8) | blob[p+4]
        p += 5
        chans.append((route, cmd, mod))
    patch_ptr = (blob[p] << 8) | blob[p+1]
    print(f"patch_table_ptr={patch_ptr:#x}")
    # tick -> seconds: accumulator adds 16/frame (default), event-tick when >= tempo_base
    # => seconds = ticks * tempo_base/16 / 60
    scale = tempo_base / 16 / 60
    for route, cmd, mod in chans:
        r = walk(blob, cmd)
        intro = r["loop_tick"]
        body = r["loop_body_ticks"]
        print(f"{ROUTES.get(route,route):>4} cmd={cmd:#06x} mod={mod:#06x} "
              f"total_ticks={r['ticks']:5d} ({r['ticks']*scale:6.2f}s) "
              f"term={r['terminator']:<6} notes={r['notes']:5d} "
              f"loop@tick={intro if intro is not None else '-':>5} "
              f"body_ticks={body if body is not None else '-':>5} "
              f"({(body*scale if body else 0):6.2f}s body)")

if __name__ == "__main__":
    main(sys.argv[1])
