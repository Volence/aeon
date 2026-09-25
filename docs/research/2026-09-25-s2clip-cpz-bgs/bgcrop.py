"""Native-palette BG lowering cost for EHZ and CPZ: tiles after pixel dedupe (flips kept as
nametable bits), per candidate vertical span and 64-column crop start; seam cost like
gen_region_bg_showcase (pixel columns differing across the one invented join)."""
import sys
sys.path.insert(0, 'tools')
import numpy as np
import s2_donor as sd

def load(zone):
    d = 's2disasm'
    ch = sd.load_chunks(zone, d); bl = sd.load_blocks(zone, d)
    return sd.load_bg_grid(zone, d).astype('int64'), sd.chunk_tiles(ch, bl), bytes(sd.load_art(zone, d))

def canon(art, t):
    raw = art[t * 32:(t + 1) * 32]
    px = np.array([[(raw[r * 4 + c // 2] >> (4 if c % 2 == 0 else 0)) & 15 for c in range(8)] for r in range(8)])
    forms = [px, px[:, ::-1], px[::-1, :], px[::-1, ::-1]]
    return min(f.tobytes() for f in forms)

for zone, spans in (('EHZ', (224, 256)), ('CPZ', (512, 688, 896))):
    bg, ct, art = load(zone)
    period = {'EHZ': 4, 'CPZ': 6}[zone]
    tpc = ct.shape[1]
    for span in spans:
        rows_c = -(-span // 128)
        full = ct[bg[:rows_c, :period]].transpose(0, 2, 1, 3).reshape(rows_c * tpc, period * tpc)[:span // 8]
        ext = np.concatenate([full, full], axis=1)
        best = None
        for s in range(period):
            crop = ext[:, s * tpc:s * tpc + 64]
            idx = set(int(w) & 0x7FF for w in crop.ravel())
            pix = set(canon(art, t) for t in idx)
            # seam: tile column after crop vs crop's first column (word equality proxy)
            nxt = ext[:, s * tpc + 64] if full.shape[1] > 64 else ext[:, s * tpc]
            seam = int((nxt != crop[:, 0]).sum())
            prio = int(((crop & 0x8000) != 0).sum())
            cand = (seam, s, len(idx), len(pix), prio)
            print(f"  {zone} span {span}px ({span//8} rows) crop start chunk {s}: idx tiles {len(idx)}, pixel-dedupe tiles {len(pix)}, seam-mismatch cells {seam}, priority cells {prio}")
            if full.shape[1] == 64:
                break
