import sys, struct, collections
sys.path.insert(0, 'tools')
import numpy as np
import s2_donor as sd
aeon0 = struct.unpack('>H', open('art/palettes/SonicAndTails.bin', 'rb').read()[:2])[0]
print(f"aeon backdrop = CRAM line0 entry0 = ${aeon0:03X}")
for zone, rows_px, crop_cols in (('EHZ', 224, 64), ('CPZ', 688, 64)):
    donor = 's2disasm'
    chunks = sd.load_chunks(zone, donor); blocks = sd.load_blocks(zone, donor)
    ct = sd.chunk_tiles(chunks, blocks)
    bg = sd.load_bg_grid(zone, donor).astype('int64')
    art = bytes(sd.load_art(zone, donor))
    pal = struct.unpack('>48H', sd.read_bytes(sd.palette_path(zone, donor)))
    backdrop = pal[16]  # $8720: line 2 entry 0 -> palette.bin holds lines 1-3, so line2 is index 16
    tpc = ct.shape[1]
    rows_c = (rows_px + 127) // 128
    full = ct[bg[:rows_c, :8]].transpose(0, 2, 1, 3).reshape(rows_c * tpc, 8 * tpc)
    full = full[:rows_px // 8, :crop_cols]
    tot = trans = 0
    for w in full.ravel():
        w = int(w); t = w & 0x7FF
        raw = art[t * 32:(t + 1) * 32]
        for b in raw:
            for v in (b >> 4, b & 15):
                tot += 1
                trans += (v == 0)
    # line-0 words
    l0 = sum(1 for w in full.ravel() if int(w) & 0x7FF and ((int(w) >> 13) & 3) == 0)
    print(f"{zone}: visible BG {rows_px}px x {crop_cols*8}px: transparent px {trans}/{tot} = {100*trans/tot:.1f}%; donor backdrop (line2 e0) ${backdrop:03X}; line-0 words {l0}")
    # palette entries used per line (to see free entries)
    used = collections.defaultdict(set)
    for w in full.ravel():
        w = int(w); t = w & 0x7FF; ln = (w >> 13) & 3
        for b in art[t * 32:(t + 1) * 32]:
            used[ln].add(b >> 4); used[ln].add(b & 15)
    print('   BG entries used per line', {k: sorted(v) for k, v in used.items()})
    # does donor palette contain backdrop colour at a nonzero index?
    hits = [(i // 16 + 1, i % 16) for i, c in enumerate(pal) if c == backdrop and i % 16 != 0]
    print('   backdrop colour also at (line, entry):', hits)
