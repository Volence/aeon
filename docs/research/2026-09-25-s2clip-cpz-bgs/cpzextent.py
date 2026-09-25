import sys
sys.path.insert(0, 'tools')
import numpy as np
import s2_donor as sd
zone, donor = 'CPZ', 's2disasm'
chunks = sd.load_chunks(zone, donor); blocks = sd.load_blocks(zone, donor)
ct = sd.chunk_tiles(chunks, blocks)
fg = sd.load_fg_grid(zone, donor).astype('int64')
tpc = ct.shape[1]
full = ct[fg].transpose(0, 2, 1, 3).reshape(fg.shape[0] * tpc, fg.shape[1] * tpc)
print('fg tile grid', full.shape)
for x0 in range(0, 10432, 2048):
    band = full[:, x0 // 8:(x0 + 2048) // 8] & 0x7FF
    rows = np.where(band.any(axis=1))[0]
    print(f"x {x0}..{x0+2047}: painted tile rows {rows.min()*8}..{rows.max()*8+7} px")
# chunk-level: which chunk rows are non-zero in first 16 chunk cols
for sec in range(6):
    sub = fg[:, sec * 16:(sec + 1) * 16]
    nzr = [r for r in range(sub.shape[0]) if sub[r].any()]
    print('section', sec, 'nonzero chunk rows', nzr)
