"""Blocks (16x16) where plane A and plane B differ, inside a clip rect, and whether each
touches air that is open on BOTH planes (i.e. a player could be beside it)."""
import sys
import numpy as np
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import render as R

zone, w, h = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
A, B = R.masks(zone)
A, B = A[:h, :w] > 0, B[:h, :w] > 0
H, W = h // 16, w // 16
blkA = A.reshape(H, 16, W, 16).any(axis=(1, 3))
blkB = B.reshape(H, 16, W, 16).any(axis=(1, 3))
diff = (A != B).reshape(H, 16, W, 16).any(axis=(1, 3))
air_both = ~blkA & ~blkB
near = np.zeros_like(air_both)
p = np.pad(air_both, 1)
for dy in (0, 1, 2):
    for dx in (0, 1, 2):
        near |= p[dy:dy + H, dx:dx + W]
exposed = diff & near

onlyA_blk = ((A != B) & A).reshape(H, 16, W, 16).any(axis=(1, 3))
seen = np.zeros_like(exposed); clusters = []
for y0, x0 in zip(*np.nonzero(exposed)):
    if seen[y0, x0]: continue
    st = [(y0, x0)]; seen[y0, x0] = True; cells = []
    while st:
        y, x = st.pop(); cells.append((y, x))
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                yy, xx = y + dy, x + dx
                if 0 <= yy < H and 0 <= xx < W and exposed[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True; st.append((yy, xx))
    clusters.append(cells)
print(f"{zone} rect {w}x{h}: differing blocks {int(diff.sum())}, exposed {int(exposed.sum())}, clusters {len(clusters)}")
for c in sorted(clusters, key=lambda c: (min(x for _, x in c))):
    ys = [y for y, _ in c]; xs = [x for _, x in c]
    na = sum(1 for y, x in c if onlyA_blk[y, x])
    print(f"  x {min(xs)*16}..{(max(xs)+1)*16} y {min(ys)*16}..{(max(ys)+1)*16}: {len(c)} blocks, {na} carry A-only pixels")
