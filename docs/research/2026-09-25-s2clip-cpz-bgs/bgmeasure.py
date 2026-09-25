import sys, os, struct, collections
sys.path.insert(0, 'tools')
import numpy as np
import s2_donor as sd
for zone in sys.argv[1:]:
    donor = 's2disasm'
    chunks = sd.load_chunks(zone, donor); blocks = sd.load_blocks(zone, donor)
    bg = sd.load_bg_grid(zone, donor).astype('int64'); ct = sd.chunk_tiles(chunks, blocks)
    fg = sd.load_fg_grid(zone, donor).astype('int64')
    art = sd.load_art(zone, donor)
    tpc = ct.shape[1]
    painted = [r for r in range(bg.shape[0]) if any((ct[c] & 0x7FF).any() for c in set(bg[r].tolist()))]
    nz = [c for c in range(bg.shape[1]) if bg[:, c].any()]
    width = max(nz) + 1
    rows_c = max(painted) + 1
    period = next((p for p in range(1, width) if all((bg[r, :width - p] == bg[r, p:width]).all() for r in range(rows_c))), None)
    print(f"== {zone}: bg grid {bg.shape}, painted chunk rows {painted} (={rows_c*128}px tall), painted width {width} chunks ({width*128}px), period {period} chunks ({(period or 0)*128}px); art tiles {len(art)//32}")
    W = width if period is None else period
    full = ct[bg[:rows_c, :W]].transpose(0, 2, 1, 3).reshape(rows_c * tpc, W * tpc)
    words = full.ravel()
    lines = collections.Counter(((int(w) >> 13) & 3) for w in words if int(w) & 0x7FF)
    prio = sum(1 for w in words if int(w) & 0x8000)
    tiles = set(int(w) & 0x7FF for w in words)
    print(f"   one period: {full.shape[1]} cols x {full.shape[0]} rows; distinct tile idx {len(tiles)}; palette lines {dict(lines)}; prio cells {prio}/{len(words)}")
    if full.shape[1] >= 64:
        ext = np.concatenate([full, full], axis=1)
        counts = [len(set(int(w) & 0x7FF for w in ext[:, s:s + 64].ravel())) for s in range(0, full.shape[1], 8)]
        print(f"   64-col crops: distinct tiles min {min(counts)} max {max(counts)}")
    fgt = set()
    for c in set(fg.ravel().tolist()):
        fgt |= set((ct[c] & 0x7FF).ravel().tolist())
    print(f"   bg tiles also used by fg: {len(tiles & fgt)}; bg-only: {len(tiles - fgt)}")
    for r in range(rows_c):
        rt = set(int(w) & 0x7FF for w in full[r * tpc:(r + 1) * tpc].ravel())
        print(f"   chunk row {r} (y {r*128}..{r*128+127}): {len(rt)} distinct tiles, chunk ids {sorted(set(bg[r, :W].tolist()))[:24]}")
