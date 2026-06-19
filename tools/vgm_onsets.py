#!/usr/bin/env python3
"""Parse a VGM file into per-channel YM2612 note-onset timelines.

Used to compare our Moving Trucks port against the live B&R reference capture:
extracts, per FM channel, every key-on (reg $28) with its sample time and the
F-number/block latched at that moment (-> approximate note), so we can diff the
per-channel onset *cadence* (the "out of sync" symptom) and pitch.

Usage:
  python3 tools/vgm_onsets.py <file.vgm> [--first N] [--csv out.csv]
"""
import sys, struct, math

# YM2612 reg $28 channel-select nibble -> logical FM channel (1..6)
KEYON_CH = {0: 1, 1: 2, 2: 3, 4: 4, 5: 5, 6: 6}

def read_u32(b, o): return struct.unpack_from('<I', b, o)[0]

def parse(path):
    with open(path, 'rb') as f:
        b = f.read()
    assert b[:4] == b'Vgm ', 'not a VGM file'
    version = read_u32(b, 0x08)
    ym_clock = read_u32(b, 0x2C)
    data_off = read_u32(b, 0x34)
    start = 0x40 if (version < 0x150 or data_off == 0) else 0x34 + data_off
    total_samples_hdr = read_u32(b, 0x18)

    # per-channel latched fnum-low(part), fnum-high+block; events list
    fnum_low = {c: 0 for c in range(1, 7)}   # ch1-3 from port0 $A0-$A2, ch4-6 from port1
    fnum_hi  = {c: 0 for c in range(1, 7)}   # $A4-$A6 (block<<3 | fnum_hi)
    prev_mask = {c: 0 for c in range(1, 7)}
    events = []  # (sample, ch, kind, opmask, fnum, block)

    t = 0
    i = start
    n = len(b)
    end = False
    while i < n and not end:
        cmd = b[i]; i += 1
        if cmd == 0x66:
            end = True
        elif cmd == 0x62:
            t += 735
        elif cmd == 0x63:
            t += 882
        elif cmd == 0x61:
            t += struct.unpack_from('<H', b, i)[0]; i += 2
        elif 0x70 <= cmd <= 0x7F:
            t += (cmd & 0x0F) + 1
        elif 0x80 <= cmd <= 0x8F:
            # YM2612 $2A DAC write from data bank + wait (low nibble)
            t += (cmd & 0x0F)
        elif cmd == 0x50:      # PSG
            i += 1
        elif cmd == 0x4F:      # GG stereo
            i += 1
        elif cmd in (0x52, 0x53):   # YM2612 port0/port1
            reg = b[i]; val = b[i+1]; i += 2
            port = 0 if cmd == 0x52 else 1
            if reg == 0x28 and port == 0:
                sel = val & 0x07
                mask = (val >> 4) & 0x0F
                ch = KEYON_CH.get(sel)
                if ch is not None:
                    hi = fnum_hi[ch]
                    block = (hi >> 3) & 0x07
                    fnum = ((hi & 0x07) << 8) | fnum_low[ch]
                    if mask != 0:
                        events.append((t, ch, 'on', mask, fnum, block))
                    else:
                        events.append((t, ch, 'off', 0, fnum, block))
                    prev_mask[ch] = mask
            elif 0xA0 <= reg <= 0xA2:
                ch = (reg - 0xA0) + (1 if port == 0 else 4)
                fnum_low[ch] = val
            elif 0xA4 <= reg <= 0xA6:
                ch = (reg - 0xA4) + (1 if port == 0 else 4)
                fnum_hi[ch] = val
        elif cmd == 0x67:      # data block: 0x67 0x66 tt <u32 size> <data>
            assert b[i] == 0x66
            size = read_u32(b, i + 2)
            i += 2 + 4 + size
        elif cmd == 0x68:      # PCM RAM write
            i += 11
        elif cmd in (0x90, 0x91, 0x95):
            i += 4
        elif cmd == 0x92:
            i += 5
        elif cmd == 0x93:
            i += 10
        elif cmd == 0x94:
            i += 1
        elif cmd == 0xE0:      # seek PCM
            i += 4
        elif 0x51 <= cmd <= 0x5F:   # other 2-operand chip writes
            i += 2
        elif 0x30 <= cmd <= 0x3F:   # 1-operand reserved
            i += 1
        elif 0xA0 <= cmd <= 0xBF:   # 2-operand
            i += 2
        elif 0xC0 <= cmd <= 0xDF:   # 3-operand
            i += 3
        elif 0xE1 <= cmd <= 0xFF:   # 4-operand
            i += 4
        else:
            # unknown single-byte
            pass
    return dict(version=version, ym_clock=ym_clock, total_samples=t,
                total_samples_hdr=total_samples_hdr, events=events)

def fnum_to_note(fnum, block, clock):
    if fnum == 0:
        return None, 0.0
    freq = fnum * clock / (144.0 * (2 ** (20 - block)))
    if freq <= 0:
        return None, 0.0
    midi = 69 + 12 * math.log2(freq / 440.0)
    return midi, freq

NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
def note_name(midi):
    if midi is None: return '----'
    m = int(round(midi))
    return f"{NAMES[m % 12]}{m//12 - 1}"

def main():
    path = sys.argv[1]
    first = 40
    csv = None
    a = 2
    while a < len(sys.argv):
        if sys.argv[a] == '--first': first = int(sys.argv[a+1]); a += 2
        elif sys.argv[a] == '--csv': csv = sys.argv[a+1]; a += 2
        else: a += 1
    r = parse(path)
    ev = r['events']
    SR = 44100.0
    ons = [e for e in ev if e[2] == 'on']
    print(f"file: {path}")
    print(f"version=0x{r['version']:X} ym_clock={r['ym_clock']} total_samples={r['total_samples']} (~{r['total_samples']/SR:.1f}s) hdr={r['total_samples_hdr']}")
    print(f"total key-on events: {len(ons)}   total key events: {len(ev)}")
    if not ons:
        print("NO KEY-ON ACTIVITY — capture may be silent/menu only")
        return
    t0 = ons[0][0]
    print(f"first key-on at sample {t0} ({t0/SR:.3f}s) -> aligning song start to here\n")
    by_ch = {c: [] for c in range(1, 7)}
    for (t, ch, kind, mask, fnum, block) in ons:
        by_ch[ch].append((t - t0, fnum, block, mask))
    for ch in range(1, 7):
        lst = by_ch[ch]
        print(f"=== FM{ch}: {len(lst)} onsets ===")
        if not lst:
            print("  (silent)\n"); continue
        # cadence: inter-onset intervals (samples -> ms)
        rows = []
        prev = None
        for k, (dt, fnum, block, mask) in enumerate(lst[:first]):
            midi, freq = fnum_to_note(fnum, block, r['ym_clock'])
            ioi = '' if prev is None else f"+{(dt-prev)/SR*1000:6.1f}ms"
            rows.append(f"  [{k:3}] {dt/SR:8.3f}s {ioi:>10}  {note_name(midi):>4} (fnum={fnum:4} blk={block} m={mask:X})")
            prev = dt
        print('\n'.join(rows))
        print()
    if csv:
        with open(csv, 'w') as f:
            f.write("sample_rel,ch,fnum,block,mask,midi,freq\n")
            for (t, ch, kind, mask, fnum, block) in ons:
                midi, freq = fnum_to_note(fnum, block, r['ym_clock'])
                f.write(f"{t-t0},{ch},{fnum},{block},{mask},{'' if midi is None else round(midi,3)},{round(freq,2)}\n")
        print(f"wrote {csv}")

if __name__ == '__main__':
    main()
