import sys, collections
sys.path.insert(0, 'tools')
import numpy as np
import s2_donor as sd
for zone in ('EHZ', 'CPZ'):
    donor = 's2disasm'
    chunks = sd.load_chunks(zone, donor); blocks = sd.load_blocks(zone, donor)
    ct = sd.chunk_tiles(chunks, blocks)
    fg = sd.load_fg_grid(zone, donor).astype('int64')
    art = bytes(sd.load_art(zone, donor))
    words = set()
    for c in set(fg.ravel().tolist()):
        words |= set(int(w) for w in ct[c].ravel())
    used = collections.defaultdict(set)
    for w in words:
        t = w & 0x7FF; ln = (w >> 13) & 3
        for b in art[t * 32:(t + 1) * 32]:
            used[ln].add(b >> 4); used[ln].add(b & 15)
    print(zone, 'FG entries used per line', {k: sorted(v) for k, v in sorted(used.items())})
