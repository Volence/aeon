#!/usr/bin/env python3
"""Compare per-note MODULATION/EFFECTS between two VGM register logs of the same tune.

OURS vs ORACLE for: hardware LFO ($22), per-channel AMS/FMS ($B4-$B6),
vibrato/pitch motion (freq-reg rewrites between key-ons), tremolo/volume
(TL-reg rewrites between key-ons), and PSG cadence/noise.
"""
import sys, struct

def read_u32(b, o): return struct.unpack_from('<I', b, o)[0]

# YM2612 reg $28 channel-select nibble -> logical FM channel (0..5)
# sel 0,1,2 = ch0,1,2 (port0); sel 4,5,6 = ch3,4,5 (port1)
SEL_CH = {0: 0, 1: 1, 2: 2, 4: 3, 5: 4, 6: 5}

def fm_ch(port, low_nibble):
    """port (0/1) + reg low nibble (0,1,2) -> logical FM channel 0..5."""
    return low_nibble + (0 if port == 0 else 3)

def parse(path):
    with open(path, 'rb') as f:
        b = f.read()
    assert b[:4] == b'Vgm ', 'not a VGM file'
    version = read_u32(b, 0x08)
    ym_clock = read_u32(b, 0x2C)
    data_off = read_u32(b, 0x34)
    start = 0x40 if (version < 0x150 or data_off == 0) else 0x34 + data_off

    ev = {
        'lfo22': [],            # (t, val) writes to $22
        'amsfms': [],           # (t, ch, val) writes to $B4-$B6 (port aware)
        'freq': [],             # (t, ch, reg, val) writes to $A0-$A6
        'tl':   [],             # (t, ch, op, reg, val) writes to $40-$4E
        'keyon':[],             # (t, ch, mask)
        'psg':  [],             # (t, byte) all PSG writes
    }

    t = 0
    i = start
    n = len(b)
    while i < n:
        cmd = b[i]; i += 1
        if cmd == 0x66:
            break
        elif cmd == 0x62:
            t += 735
        elif cmd == 0x63:
            t += 882
        elif cmd == 0x61:
            t += struct.unpack_from('<H', b, i)[0]; i += 2
        elif 0x70 <= cmd <= 0x7F:
            t += (cmd & 0x0F) + 1
        elif 0x80 <= cmd <= 0x8F:
            t += (cmd & 0x0F)          # DAC + wait
        elif cmd == 0x50:              # PSG
            ev['psg'].append((t, b[i])); i += 1
        elif cmd == 0x4F:              # GG stereo
            i += 1
        elif cmd in (0x52, 0x53):      # YM2612 port0 / port1
            reg = b[i]; val = b[i+1]; i += 2
            port = 0 if cmd == 0x52 else 1
            if reg == 0x22 and port == 0:
                ev['lfo22'].append((t, val))
            elif reg == 0x28 and port == 0:
                sel = val & 0x07
                mask = (val >> 4) & 0x0F
                ch = SEL_CH.get(sel)
                if ch is not None:
                    ev['keyon'].append((t, ch, mask))
            elif 0xB4 <= reg <= 0xB6:
                ch = fm_ch(port, reg - 0xB4)
                ev['amsfms'].append((t, ch, val))
            elif 0xA0 <= reg <= 0xA6:
                # $A0-$A2 fnum low, $A4-$A6 fnum hi/block; $A8-$AE are ch3 special
                low = reg & 0x0F
                if low <= 2:
                    ch = fm_ch(port, low)
                elif 4 <= low <= 6:
                    ch = fm_ch(port, low - 4)
                else:
                    ch = None
                if ch is not None:
                    ev['freq'].append((t, ch, reg, val))
            elif 0x40 <= reg <= 0x4E:
                # TL: reg = 0x40 + op*4 + chan_in_bank ; chan_in_bank 0,1,2
                bank_chan = (reg - 0x40) & 0x03
                if bank_chan <= 2:
                    op = (reg - 0x40) >> 2
                    ch = fm_ch(port, bank_chan)
                    ev['tl'].append((t, ch, op, reg, val))
        elif cmd == 0x67:              # data block
            assert b[i] == 0x66
            size = read_u32(b, i + 2)
            i += 2 + 4 + size
        elif cmd == 0x68:
            i += 11
        elif cmd in (0x90, 0x91, 0x95):
            i += 4
        elif cmd == 0x92:
            i += 5
        elif cmd == 0x93:
            i += 10
        elif cmd == 0x94:
            i += 1
        elif cmd == 0xE0:
            i += 4
        elif 0x51 <= cmd <= 0x5F:
            i += 2
        elif 0x30 <= cmd <= 0x3F:
            i += 1
        elif 0xA0 <= cmd <= 0xBF:
            i += 2
        elif 0xC0 <= cmd <= 0xDF:
            i += 3
        elif 0xE1 <= cmd <= 0xFF:
            i += 4
    return dict(version=version, ym_clock=ym_clock, total=t, ev=ev)

def keyon_segments(ev):
    """Per channel, build list of (start_t, end_t) segments between key-ons.
    A key-on = $28 write with mask != 0 for that channel. We split the timeline
    at each key-on event; a 'note' segment runs from one key-on to the next
    key-event (on or off) for that channel."""
    by_ch = {c: [] for c in range(6)}
    for (t, ch, mask) in ev['keyon']:
        by_ch[ch].append((t, mask))
    segs = {c: [] for c in range(6)}      # list of (start, end)
    for c in range(6):
        evs = by_ch[c]
        # iterate; whenever mask!=0 we start a note ending at next key event
        for k, (t, mask) in enumerate(evs):
            if mask != 0:
                end = evs[k+1][0] if k+1 < len(evs) else None
                segs[c].append((t, end))
    return segs, by_ch

def count_in_segments(writes_by_ch, segs):
    """For each channel, count register writes that fall strictly inside a note
    segment (after start_t, before end_t). Returns (total_mid_writes, n_notes)."""
    out = {}
    for c in range(6):
        notes = segs[c]
        if not notes:
            out[c] = (0, 0); continue
        ws = sorted(writes_by_ch.get(c, []))
        mid = 0
        wi = 0
        for (s, e) in notes:
            # count writes with s < t and (e is None or t < e)
            for t in ws:
                if t > s and (e is None or t < e):
                    mid += 1
        out[c] = (mid, len(notes))
    return out

def fmt_table(title, ours, oracle, perch=True):
    print(title)
    if perch:
        print(f"  {'ch':>3} | {'OURS mid/notes (avg)':>26} | {'ORACLE mid/notes (avg)':>26}")
        for c in range(6):
            om, on = ours[c]
            rm, rn = oracle[c]
            oa = (om/on) if on else 0.0
            ra = (rm/rn) if rn else 0.0
            print(f"  FM{c} | {om:6} / {on:4}  = {oa:7.2f} | {rm:6} / {rn:4}  = {ra:7.2f}")
    print()

def main():
    ours_path = sys.argv[1]
    oracle_path = sys.argv[2]
    O = parse(ours_path)
    R = parse(oracle_path)
    SR = 44100.0
    print("="*78)
    print(f"OURS   = {ours_path}")
    print(f"         ym_clock={O['ym_clock']} dur~{O['total']/SR:.1f}s "
          f"keyons={sum(1 for _,_,m in O['ev']['keyon'] if m)} ")
    print(f"ORACLE = {oracle_path}")
    print(f"         ym_clock={R['ym_clock']} dur~{R['total']/SR:.1f}s "
          f"keyons={sum(1 for _,_,m in R['ev']['keyon'] if m)} ")
    print("="*78); print()

    # ---- 1. Hardware LFO ($22) ----
    def lfo_summary(P):
        ws = P['ev']['lfo22']
        nz = [v for (_, v) in ws if v != 0]
        enabled = [v for v in nz if v & 0x08]
        freqs = sorted(set(v & 0x07 for v in enabled))
        return len(ws), len(nz), len(enabled), freqs
    o = lfo_summary(O); r = lfo_summary(R)
    print("[1] HARDWARE LFO (reg $22)")
    print(f"  OURS:   {o[0]} writes, {o[1]} nonzero, {o[2]} with enable bit3 set, freqs={o[3]}")
    print(f"  ORACLE: {r[0]} writes, {r[1]} nonzero, {r[2]} with enable bit3 set, freqs={r[3]}")
    print()

    # ---- 2. AMS/FMS ($B4-$B6) ----
    def amsfms_summary(P):
        per = {c: {'L':set(),'R':set(),'AMS':set(),'FMS':set(),'n':0} for c in range(6)}
        for (t, ch, val) in P['ev']['amsfms']:
            d = per[ch]
            d['n'] += 1
            d['L'].add((val>>7)&1); d['R'].add((val>>6)&1)
            d['AMS'].add((val>>4)&3); d['FMS'].add(val&7)
        return per
    o = amsfms_summary(O); r = amsfms_summary(R)
    print("[2] AMS / FMS (reg $B4-$B6)  [AMS gates tremolo, FMS gates vibrato from HW LFO]")
    print(f"  {'ch':>3} | {'OURS AMS/FMS seen':>22} | {'ORACLE AMS/FMS seen':>22}")
    for c in range(6):
        oa = sorted(o[c]['AMS']); of = sorted(o[c]['FMS'])
        ra = sorted(r[c]['AMS']); rf = sorted(r[c]['FMS'])
        print(f"  FM{c} | AMS{oa} FMS{of} (n={o[c]['n']}) | AMS{ra} FMS{rf} (n={r[c]['n']})")
    print()

    # ---- 3. VIBRATO / pitch motion: freq rewrites between key-ons ----
    Oseg, _ = keyon_segments(O['ev'])
    Rseg, _ = keyon_segments(R['ev'])
    def freq_by_ch(P):
        d = {c: [] for c in range(6)}
        for (t, ch, reg, val) in P['ev']['freq']:
            d[ch].append(t)
        return d
    of = count_in_segments(freq_by_ch(O), Oseg)
    rf = count_in_segments(freq_by_ch(R), Rseg)
    print("[3] VIBRATO / PITCH MOTION  (freq-reg $A0-$A6 rewrites strictly INSIDE a held note)")
    fmt_table("    avg = mid-note freq writes per note (>0 = software pitch motion)", of, rf)

    # ---- 4. TREMOLO / volume: TL rewrites between key-ons ----
    def tl_by_ch(P):
        d = {c: [] for c in range(6)}
        for (t, ch, op, reg, val) in P['ev']['tl']:
            d[ch].append(t)
        return d
    ot = count_in_segments(tl_by_ch(O), Oseg)
    rt = count_in_segments(tl_by_ch(R), Rseg)
    print("[4] TREMOLO / VOLUME ENVELOPE  (TL-reg $40-$4E rewrites strictly INSIDE a held note)")
    fmt_table("    avg = mid-note TL writes per note (>0 = software volume ramp/tremolo)", ot, rt)

    # ---- 5. PSG ----
    def psg_summary(P):
        vol_writes = 0    # latched volume bytes (0x9x,0xBx,0xDx,0xFx with bit4 set => attenuation)
        tone_writes = 0
        noise_ctrl = 0    # 0xEx = noise control
        noise_vol_active = False
        # PSG byte: bit7=1 latch (cc t ...), bit4 = type (0=tone/2nd, 1=volume)
        # channel = bits 5-6. reg type: latch byte 1ccrdddd, r=1 -> volume
        attn_per_ch = {0:[],1:[],2:[],3:[]}
        latched_ch = 0; latched_type = 0
        for (t, byte) in P['ev']['psg']:
            if byte & 0x80:
                ch = (byte >> 5) & 3
                typ = (byte >> 4) & 1   # 1 = volume/attenuation
                latched_ch = ch; latched_type = typ
                if ch == 3 and typ == 0:
                    noise_ctrl += 1     # noise control register write
                if typ == 1:
                    vol_writes += 1
                    attn_per_ch[ch].append((t, byte & 0x0F))
                else:
                    tone_writes += 1
            else:
                # data byte continues last latched reg
                if latched_type == 1:
                    vol_writes += 1
                    attn_per_ch[latched_ch].append((t, byte & 0x0F))
                else:
                    tone_writes += 1
        # noise channel ever audible? attenuation < 15 on ch3
        noise_active = any(a < 15 for (_, a) in attn_per_ch[3])
        return dict(total=len(P['ev']['psg']), vol=vol_writes, tone=tone_writes,
                    noise_ctrl=noise_ctrl, noise_active=noise_active,
                    attn=attn_per_ch)
    o = psg_summary(O); r = psg_summary(R)
    print("[5] PSG  (volume/attenuation cadence + noise usage)")
    print(f"  {'metric':>22} | {'OURS':>12} | {'ORACLE':>12}")
    print(f"  {'total PSG writes':>22} | {o['total']:>12} | {r['total']:>12}")
    print(f"  {'volume/attn writes':>22} | {o['vol']:>12} | {r['vol']:>12}")
    print(f"  {'tone/freq writes':>22} | {o['tone']:>12} | {r['tone']:>12}")
    print(f"  {'noise-ctrl writes':>22} | {o['noise_ctrl']:>12} | {r['noise_ctrl']:>12}")
    print(f"  {'noise audible (ch3)':>22} | {str(o['noise_active']):>12} | {str(r['noise_active']):>12}")
    # per-channel distinct attenuation levels (volume envelope richness)
    print("  distinct attenuation levels per PSG channel (more = volume envelopes):")
    for c in range(4):
        olv = sorted(set(a for (_,a) in o['attn'][c]))
        rlv = sorted(set(a for (_,a) in r['attn'][c]))
        oc = len(o['attn'][c]); rc = len(r['attn'][c])
        print(f"    PSG{c}: OURS {oc} writes, {len(olv)} levels {olv} | "
              f"ORACLE {rc} writes, {len(rlv)} levels {rlv}")
    print()

if __name__ == '__main__':
    main()
