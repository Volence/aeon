#!/usr/bin/env python3
"""Pin down the FM2 bass 'white-noise / clap on the attack' artifact objectively:
isolate FM2 (drop every other channel's key-on + the DAC + PSG so only the bass
sounds), render to WAV via vgm2wav, then FFT each bass hit and measure how NOISY it
is (spectral flatness + high-frequency energy ratio). Compare OURS vs the B&R
reference, hit by hit over the first beats. White noise -> high spectral flatness +
high HF ratio; a clean tonal bass -> low both.

Usage: fm2_noise_analysis.py <ours.vgm> <bnr.vgm>
"""
import struct, sys, subprocess, wave, tempfile, os
import numpy as np

def filter_fm2(path, out):
    """Keep FM2 (port-0 ch1) only: drop $28 key events for other channels, drop all
    port-1 ($53) writes (FM4/5/6), drop DAC ($2A) and PSG ($50). Keep waits + FM2/
    global $52 writes. Returns list of FM2 key-ON sample times (VGM samples @44100)."""
    b = open(path, 'rb').read()
    ver = struct.unpack_from('<I', b, 8)[0]; do = struct.unpack_from('<I', b, 0x34)[0]
    start = 0x40 if (ver < 0x150 or do == 0) else 0x34 + do
    out_data = bytearray(b[:start])          # copy header verbatim
    i = start; n = len(b); clk = 0; keyons = []; pitches = []
    a1 = a5 = 0                              # FM2 fnum lo/hi shadow (for alignment)
    while i < n:
        cmd = b[i]
        if cmd == 0x66:
            out_data.append(cmd); break
        elif cmd == 0x52:                      # YM port 0
            r = b[i+1]; v = b[i+2]; keep = True
            if r == 0xA1: a1 = v
            elif r == 0xA5: a5 = v
            if r == 0x28:
                if (v & 7) != 1: keep = False              # other channel key event
                elif (v >> 4) & 0xF:                       # FM2 key-ON
                    keyons.append(clk)
                    pitches.append((((a5 >> 3) & 7), ((a5 & 7) << 8) | a1))  # (block,fnum)
            elif r == 0x2A: keep = False                   # DAC data
            if keep: out_data += b[i:i+3]
            i += 3
        elif cmd == 0x53: i += 3               # YM port 1 (FM4/5/6) -> drop
        elif cmd == 0x50: i += 2               # PSG -> drop
        elif cmd == 0x4f: out_data += b[i:i+2]; i += 2     # GG stereo (keep)
        elif cmd == 0x61:
            clk += struct.unpack_from('<H', b, i+1)[0]; out_data += b[i:i+3]; i += 3
        elif cmd == 0x62: clk += 735; out_data.append(cmd); i += 1
        elif cmd == 0x63: clk += 882; out_data.append(cmd); i += 1
        elif 0x70 <= cmd <= 0x7f:
            clk += (cmd & 0xf) + 1; out_data.append(cmd); i += 1
        elif cmd == 0x67:                      # data block -> skip (don't copy)
            sz = struct.unpack_from('<I', b, i+3)[0]; i += 7 + sz
        else:
            raise ValueError(f"unexpected VGM cmd 0x{cmd:02x} at offset {i}")
    struct.pack_into('<I', out_data, 0x04, len(out_data) - 4)   # fix EOF offset
    open(out, 'wb').write(out_data)
    return keyons, pitches

def render(vgm, wav):
    subprocess.run(['vgm2wav', '--loops', '1', '--fade', '0.0', vgm, wav],
                   check=True, capture_output=True)

def load_mono(wav):
    w = wave.open(wav, 'rb'); n = w.getnframes(); ch = w.getnchannels()
    raw = w.readframes(n); w.close()
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
    if ch == 2: a = a.reshape(-1, 2).mean(axis=1)
    return a, 44100

def hit_noise(sig, sr, keyons, win=4096, skip=128):
    """Per hit: spectral flatness (0 tonal..1 white) + HF(>3kHz) energy ratio,
    measured on a window just after the attack."""
    rows = []
    for k in keyons:
        seg = sig[k + skip : k + skip + win]
        if len(seg) < win or np.max(np.abs(seg)) < 50:     # silent/short -> skip
            rows.append(None); continue
        seg = seg * np.hanning(len(seg))
        sp = np.abs(np.fft.rfft(seg)) ** 2 + 1e-9
        freqs = np.fft.rfftfreq(win, 1 / sr)
        sfm = np.exp(np.mean(np.log(sp))) / np.mean(sp)
        hf = sp[freqs > 3000].sum() / sp.sum()
        rows.append((sfm, hf))
    return rows

def main():
    ours, bnr = sys.argv[1], sys.argv[2]
    td = tempfile.mkdtemp(); res = {}; pit = {}
    for label, path in [("OURS", ours), ("B&R", bnr)]:
        fv = os.path.join(td, f"{label}.vgm"); wv = os.path.join(td, f"{label}.wav")
        ko, p = filter_fm2(path, fv); render(fv, wv)
        sig, sr = load_mono(wv); rows = hit_noise(sig, sr, ko)   # one row per key-on (None if skipped)
        res[label] = rows; pit[label] = p
        ana = [r for r in rows if r is not None]
        print(f"{label}: {len(ko)} FM2 key-ons, {len(ana)} analyzable hits, "
              f"WAV {len(sig)/sr:.1f}s peak {np.max(np.abs(sig)):.0f}")

    # --- ALIGN by FM2 pitch sequence (skip B&R's menu prefix) ---
    op, rp = pit['OURS'], pit['B&R']
    W = 48; best = (-1, 0)
    for d in range(max(1, len(rp) - W)):
        m = sum(1 for j in range(W) if j < len(op) and rp[d + j] == op[j])
        if m > best[0]: best = (m, d)
    d = best[1]
    print(f"\nAligned OURS[0] -> B&R[{d}] ({best[0]}/{W} pitch match). "
          f"Per-hit noise at the SAME song position (SFM 0..1):")
    print(f"{'songhit':>7} | {'pitch':>8} | {'OURS sfm':>9} | {'B&R sfm':>8} | verdict")
    for j in range(20):
        o = res['OURS'][j] if j < len(res['OURS']) else None
        r = res['B&R'][d + j] if d + j < len(res['B&R']) else None
        if o is None or r is None: continue
        pn = op[j] if j < len(op) else ('?', '?')
        verdict = ""
        if o[0] > 0.2 and r[0] <= 0.2: verdict = "<<< OURS noisy, B&R CLEAN"
        elif o[0] > 0.2 and r[0] > 0.2: verdict = "both noisy (authentic)"
        print(f"{j:>7} | blk{pn[0]} fn{pn[1]:<4} | {o[0]:>9.3f} | {r[0]:>8.3f} | {verdict}")
    # which hits are NOISY (SFM > 0.2) — reveals the period + the menu offset
    for label in ("OURS", "B&R"):
        rows = [x for x in res[label] if x is not None]
        noisy = [j for j, x in enumerate(rows) if x[0] > 0.2]
        diffs = [b - a for a, b in zip(noisy, noisy[1:])]
        from collections import Counter
        period = Counter(diffs).most_common(1)[0] if diffs else ("-", 0)
        print(f"\n{label}: {len(noisy)}/{len(rows)} noisy hits (SFM>0.2). "
              f"first 8 noisy indices: {noisy[:8]}  dominant gap: {period[0]} (x{period[1]})")

if __name__ == '__main__':
    main()
