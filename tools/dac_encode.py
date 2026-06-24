# tools/dac_encode.py  — offline noise-shaped 4-bit DPCM (DPCM-HQ)
import numpy as np

# starting delta families (sharp-transient / body / quiet). Signed 8-bit, mod-256.
DELTA_TABLES = [
    [0,1,2,4,8,16,32,64,-128,-1,-2,-4,-8,-16,-32,-64],     # 0: sharp transients
    [-34,-21,-13,-8,-5,-3,-2,-1,0,1,2,3,5,8,13,21],        # 1: body
    [-20,-12,-8,-6,-4,-3,-2,-1,0,1,2,3,4,6,8,12],          # 2: quiet/tails
]

def decode_dpcm(nibble_bytes, table, seed=0x80):
    acc = seed & 0xFF
    out = []
    for byte in nibble_bytes:
        for nib in ((byte >> 4) & 0xF, byte & 0xF):        # high nibble first
            acc = (acc + table[nib]) & 0xFF
            out.append(acc)
    return np.array(out, dtype=np.uint8)

def encode_dpcm(samples, table_index=None, seed=0x80):
    """Greedy nearest-delta with error-feedback noise shaping. Returns (packed_bytes, table_index).
    No clamp: the predictor wraps mod-256 exactly like the Z80 decoder. If table_index is None,
    tries all DELTA_TABLES and keeps the best-correlating one."""
    samples = np.asarray(samples, dtype=np.int32)
    candidates = range(len(DELTA_TABLES)) if table_index is None else [table_index]
    best = None
    for ti in candidates:
        table = DELTA_TABLES[ti]
        acc = seed & 0xFF
        err = 0.0
        nibbles = []
        for s in samples:
            target = s + err                               # push prior quant error forward
            bestn, bestd = 0, 1e9
            for n, d in enumerate(table):
                val = (acc + d) & 0xFF
                dist = min(abs(val - target), 256 - abs(val - target))   # shortest wrap distance
                if dist < bestd:
                    bestn, bestd = n, dist
            acc = (acc + table[bestn]) & 0xFF
            err = float(s) - float(acc)
            nibbles.append(bestn)
        if len(nibbles) & 1:
            nibbles.append(0)
        packed = bytes((nibbles[i] << 4) | nibbles[i+1] for i in range(0, len(nibbles), 2))
        score = np.corrcoef(samples.astype(float),
                            decode_dpcm(packed, table, seed)[:len(samples)].astype(float))[0, 1]
        if best is None or score > best[2]:
            best = (packed, ti, score)
    return best[0], best[1]                                 # (packed_bytes, table_index)

def _read_wav_u8(path):
    import wave
    w = wave.open(path, 'rb')
    assert w.getsampwidth() == 1 and w.getnchannels() == 1, "expect 8-bit mono wav"
    n = w.getnframes(); rate = w.getframerate()
    data = np.frombuffer(w.readframes(n), dtype=np.uint8).astype(np.int32)  # unsigned 8-bit, centered 128
    w.close()
    return data, rate

def _resample_linear(samples, src_rate, dst_rate):
    if dst_rate == src_rate:
        return samples
    n_out = max(1, round(len(samples) * dst_rate / src_rate))
    xs = np.linspace(0, len(samples) - 1, n_out)
    return np.interp(xs, np.arange(len(samples)), samples).round().astype(np.int32)

if __name__ == "__main__":
    import sys, argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("wav"); ap.add_argument("dpcm")
    ap.add_argument("--rate", type=int, default=0, help="resample to this Hz (0 = native, no resample)")
    ap.add_argument("--table", type=int, default=None, help="force a delta-table index (default: auto-select)")
    a = ap.parse_args()
    samples, src_rate = _read_wav_u8(a.wav)
    if a.rate:
        samples = _resample_linear(samples, src_rate, a.rate)
    packed, ti = encode_dpcm(samples, table_index=a.table)
    open(a.dpcm, "wb").write(packed)
    print(f"{a.dpcm}: table={ti} samples={len(samples)} dpcm_bytes={len(packed)} src_rate={src_rate}")
