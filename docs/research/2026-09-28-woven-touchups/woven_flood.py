#!/usr/bin/env python3
"""Research instrument for docs/research/2026-09-28-woven-touchups.md (not a gate, not a tool): a GENEROUS reachability flood over the BAKED woven act.

Reads the baked strips (the same bytes clip_reachability.StripGeometry reads) and the emitted
solidity/heightmap tables. Model, deliberately generous so that "unreachable" is a strong claim:
  * cells are 8 px wide x 16 px tall (COLL_CELL_W x COLL_CELL_H), union of both planes:
      floor  = top-solid with a positive height in the sensor column on EITHER plane
      wall   = LRB-solid on BOTH planes (blocks sideways / upward / occupancy)
      fall-through = a falling body passes a cell unless it is a floor on BOTH planes
  * the player is a POINT one cell tall (no body height), so any 16-px gap is passable.
  * standing spot = a non-wall cell whose cell below is a floor.
  * walk: to the next column if a standing spot exists within UP_STEP rows up / 1 row down;
    otherwise walk off: fall straight down that column.
  * jump: an air flood through non-wall cells, up to JR rows above the launch row, within
    H columns either side; every air cell over a floor is a landing; an air cell on the box's
    bottom edge falls straight down.
No objects (springs, platforms, bridges): the act carries none.
"""
import os, sys, json, collections
import numpy as np

WT = os.getcwd()
sys.path.insert(0, os.path.join(WT, "tools"))
import clip_reachability as CR
import clip_manifest as CM

UP_STEP = int(os.environ.get("UP_STEP", 2))     # rows a walk may climb per 8-px column (slopes)
JR = int(os.environ.get("JR", 6))               # 99 px (JUMP_RISE_MAX) // 16
H = int(os.environ.get("HCOLS", 48))            # 384 px of horizontal air travel
BOXDOWN = 24

man = sys.argv[1]
act = CM.load(man, donor_root=CM._root(None))
gw, gh = 5, 4
import clip_rom_bake as _CRB
_CRB.require_stamp(act.id, CR.GEN_DIR, "woven_flood (scratch)")   # never measure another act's bytes
geo = CR.StripGeometry(CR.GEN_DIR, gw, act.section_px)
sol = open(os.path.join(CR.COLL_DIR, "solidity.bin"), "rb").read()
hm = open(os.path.join(CR.COLL_DIR, "heightmaps.bin"), "rb").read()
W, Hh = gw * 2048 // 8, gh * 2048 // 16
attr = np.zeros((2, Hh, W), dtype=np.int32)
tpr = geo.tile_rows
for n in range(gw * gh):
    sx, sy = n % gw, n // gw
    d = np.frombuffer(geo._strip(n), dtype=np.uint8).reshape(tpr, geo.stride)
    for p in (0, 1):
        blk = d[:, geo.nt_bytes + p * geo.coll_rows: geo.nt_bytes + (p + 1) * geo.coll_rows]
        attr[p, sy * geo.coll_rows:(sy + 1) * geo.coll_rows, sx * tpr:(sx + 1) * tpr] = blk.T
solarr = np.frombuffer(sol, dtype=np.uint8)
hmarr = np.frombuffer(hm, dtype=np.int8).reshape(-1, 16)
cols = np.arange(W)
sensor = ((cols * 8 + 4) & 15)
floor_p = np.zeros((2, Hh, W), dtype=bool)
full_p = np.zeros((2, Hh, W), dtype=bool)
lrb_p = np.zeros((2, Hh, W), dtype=bool)
for p in (0, 1):
    a = attr[p]
    s_ = solarr[a]
    h = hmarr[a, sensor[None, :].repeat(Hh, 0)]
    solid = (a != 0) & ((s_ & 3) != 0)
    floor_p[p] = (a != 0) & ((s_ & 1) != 0) & (h > 0)
    lrb_p[p] = (a != 0) & ((s_ & 2) != 0)
    # a cell the body cannot be in: solid with a full column (16) or hanging (negative)
    full_p[p] = solid & ((h >= 16) | (h < 0))
FLOOR_ANY = floor_p[0] | floor_p[1]
FLOOR_BOTH = floor_p[0] & floor_p[1]
WALL = (full_p[0] & lrb_p[0]) & (full_p[1] & lrb_p[1])
FREE = ~WALL

CONN = list(act.corridors) + list(act.shafts)
CMAP = np.zeros((Hh, W), dtype=np.int16)
for i, k in enumerate(CONN, 1):
    X, Y, w, h = k.dst
    CMAP[Y // 16:(Y + h) // 16, X // 8:(X + w) // 8] = i
TOUCH = set()


def is_stand(r, c):
    """the cell holding the feet: a free cell that is itself a (partial) floor, or sits on one"""
    return 0 <= r < Hh - 1 and FREE[r, c] and (FLOOR_ANY[r, c] or FLOOR_ANY[r + 1, c])


def fall(r, c):
    """straight down from (r, c). A falling body passes any cell that is not a FLOOR (top-solid):
    Sonic 2's LRB-only interiors are solid to the sides and from below only, so a fall goes
    through them (clip_reachability's own reading). Lands in the first free cell that is or
    sits on a floor; a floor on one plane only may be passed as the other plane (generous)."""
    out = []
    while r < Hh - 1:
        if CMAP[r, c]:
            TOUCH.add(int(CMAP[r, c]))
        if FREE[r, c] and (FLOOR_ANY[r, c] or FLOOR_ANY[r + 1, c]):
            out.append((r, c))
        if FLOOR_BOTH[r, c] or (FLOOR_BOTH[r + 1, c] and not FREE[r + 1, c]):
            return out
        r += 1
    return out


PARENT = {}


def flood(seeds):
    seen = set(seeds)
    q = collections.deque(seeds)
    while q:
        r, c = q.popleft()
        nxt = []
        for dc in (-1, 1):
            c2 = c + dc
            if not 0 <= c2 < W:
                continue
            if CMAP[r, c]:
                TOUCH.add(int(CMAP[r, c]))
            found = False
            for dr in range(-UP_STEP, 2):
                r2 = r + dr
                if is_stand(r2, c2):
                    if dr < 0 and not all(FREE[r2 + k, c2] for k in range(0, -dr)):
                        continue
                    nxt.append((r2, c2)); found = True
            if not found and FREE[r, c2]:
                nxt += fall(r, c2)
        if r + 1 < Hh and not FREE[r + 1, c] and not FLOOR_ANY[r + 1, c] and not FLOOR_ANY[r, c]:
            nxt += fall(r + 1, c)
        top = max(0, r - JR)
        bot = min(Hh - 1, r + BOXDOWN)
        lo, hi = max(0, c - H), min(W - 1, c + H)
        air = {(r, c)}
        aq = [(r, c)]
        while aq:
            ar, ac = aq.pop()
            for rr, cc in ((ar - 1, ac), (ar + 1, ac), (ar, ac - 1), (ar, ac + 1)):
                if top <= rr <= bot and lo <= cc <= hi and (rr, cc) not in air and FREE[rr, cc]:
                    if rr == ar + 1 and FLOOR_BOTH[ar, ac]:
                        continue
                    air.add((rr, cc)); aq.append((rr, cc))
        for ar, ac in air:
            if CMAP[ar, ac]:
                TOUCH.add(int(CMAP[ar, ac]))
            if is_stand(ar, ac):
                nxt.append((ar, ac))
            if ar == bot:
                nxt += fall(ar, ac)
            elif ar + 1 < Hh and not FREE[ar + 1, ac] and not FLOOR_ANY[ar + 1, ac]:
                nxt += fall(ar + 1, ac)
        for s_ in nxt:
            if s_ not in seen:
                seen.add(s_); q.append(s_); PARENT[s_] = (r, c)
    return seen


start = act.raw["start"]
sr, sc = start["y"] // 16, start["x"] // 8
while not is_stand(sr, sc):
    sr += 1
seen = flood([(sr, sc)])
if os.environ.get("PATHTO"):
    px_, py_ = map(int, os.environ["PATHTO"].split(","))
    tgt = min(seen, key=lambda t: abs(t[0] * 16 - py_) + abs(t[1] * 8 - px_))
    chain = [tgt]
    while chain[-1] in PARENT:
        chain.append(PARENT[chain[-1]])
    chain.reverse()
    print("PATH to", (tgt[1] * 8, tgt[0] * 16), "in", len(chain), "moves")
    prev = None
    for r, c in chain:
        if prev is None or abs(r - prev[0]) > 1 or abs(c - prev[1]) > 1:
            print(f"   ({c * 8}, {r * 16})" + ("" if prev is None else f"  <- jump/fall from ({prev[1] * 8}, {prev[0] * 16})"))
        prev = (r, c)
    sys.exit(0)
stand = np.vstack([FREE[:-1] & (FLOOR_ANY[:-1] | FLOOR_ANY[1:]), np.zeros((1, W), bool)])
reach = np.zeros_like(stand)
for r, c in seen:
    reach[r, c] = True
print(f"model: UP_STEP={UP_STEP} JR={JR} H={H} start cell ({sr},{sc})")
print(f"standing spots: {int(stand.sum())}, reached {int(reach.sum())}")


def owner(r, c):
    x, y = c * 8, r * 16
    for k in list(act.clips) + list(act.corridors) + list(act.shafts):
        X, Y, w, h = k.dst
        if X <= x < X + w and Y <= y < Y + h:
            return k.id
    return "fill"


# components of UNREACHED standing spots (8-connected on the grid, with a 2-cell join radius)
un = stand & ~reach
lab = np.zeros(un.shape, dtype=np.int32); nl = 0
ys0, xs0 = np.nonzero(un)
for y0, x0 in zip(ys0, xs0):
    if lab[y0, x0]:
        continue
    nl += 1; lab[y0, x0] = nl; st = [(y0, x0)]
    while st:
        y, x = st.pop()
        for dy in range(-2, 3):
            for dx in range(-3, 4):
                yy, xx = y + dy, x + dx
                if 0 <= yy < un.shape[0] and 0 <= xx < un.shape[1] and un[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = nl; st.append((yy, xx))
comps = []
for i in range(1, nl + 1):
    ys, xs = np.nonzero(lab == i)
    if len(ys) == 0:
        continue
    own = collections.Counter(owner(int(y), int(x)) for y, x in zip(ys, xs))
    comps.append((len(ys), int(xs.min()) * 8, int(xs.max()) * 8 + 7, int(ys.min()) * 16,
                  int(ys.max()) * 16 + 15, own.most_common(3)))
comps.sort(reverse=True)
per = collections.Counter()
per_r = collections.Counter()
for y, x in zip(*np.nonzero(stand)):
    o = owner(int(y), int(x)); per[o] += 1
    if reach[y, x]:
        per_r[o] += 1
print("per piece: reached / standing spots")
for o in sorted(per):
    print(f"  {o:18s} {per_r[o]:6d} / {per[o]:6d}  ({100*per_r[o]/per[o]:.0f}%)")
print(f"unreached components: {len(comps)} (largest first, spots>=12)")
for n, x0, x1, y0, y1, own in comps:
    if n >= 12:
        print(f"  {n:5d} spots  x {x0}..{x1}  y {y0}..{y1}  {own}")
out = os.environ.get("OUT")
if out:
    np.save(out, reach)
    json.dump([c[:5] + (c[5],) for c in comps], open(out + ".json", "w"))

png = os.environ.get("PNG")
if png:
    from PIL import Image, ImageDraw
    img = np.zeros((Hh, W, 3), dtype=np.uint8)
    img[:] = (20, 20, 40)
    lrb_any = lrb_p[0] | lrb_p[1]
    img[lrb_any & ~WALL] = (70, 70, 90)
    img[WALL] = (110, 110, 110)
    img[FLOOR_ANY] = (160, 140, 100)
    img[stand & ~reach] = (230, 40, 40)
    img[reach] = (40, 230, 40)
    im = Image.fromarray(img).resize((W, Hh * 2), Image.NEAREST)
    d = ImageDraw.Draw(im)
    for k in list(act.clips):
        X, Y, w, h = k.dst
        d.rectangle([X // 8, Y // 8, (X + w) // 8 - 1, (Y + h) // 8 - 1], outline=(80, 160, 255))
        d.text((X // 8 + 3, Y // 8 + 3), k.id, fill=(120, 200, 255))
    for k in list(act.corridors) + list(act.shafts):
        X, Y, w, h = k.dst
        d.rectangle([X // 8, Y // 8, (X + w) // 8 - 1, (Y + h) // 8 - 1], outline=(255, 200, 0))
    im.save(png)
    crop = os.environ.get("CROP")
    if crop:
        x0, y0, x1, y1, sc = map(int, crop.split(","))
        im.crop((x0 // 8, y0 // 8, x1 // 8, y1 // 8)).resize(
            ((x1 - x0) // 8 * sc, (y1 - y0) // 8 * sc), Image.NEAREST).save(png + ".crop.png")


if os.environ.get("GRAPH"):
    def spots_in(k):
        X, Y, w, h = k.dst
        out = [(r, c) for r in range(Y // 16, (Y + h) // 16) for c in range(X // 8, (X + w) // 8)
               if is_stand(r, c)]
        if not out:   # a drop shaft: where a fall from its top row lands
            c = (X + w // 2) // 8
            out = fall(Y // 16, c)
        return out
    names = [k.id for k in CONN]
    TOUCH.clear(); flood([(sr, sc)])
    print("GRAPH start ->", sorted(names[i - 1] for i in TOUCH))
    allseen = set(seen)
    for i, k in enumerate(CONN, 1):
        TOUCH.clear()
        sd = spots_in(k)
        got = flood(sd)
        allseen |= got
        print(f"GRAPH {k.id} (seeds {len(sd)}) ->", sorted(names[j - 1] for j in TOUCH if j != i))
    ra = np.zeros_like(stand)
    for r, c in allseen:
        ra[r, c] = True
    per2 = collections.Counter()
    for y, x in zip(*np.nonzero(ra)):
        per2[owner(int(y), int(x))] += 1
    print("per piece reachable from start OR any connector:")
    for o in sorted(per):
        print(f"  {o:18s} {per2[o]:6d} / {per[o]:6d}  ({100*per2[o]/per[o]:.0f}%)")
    np.save(os.environ["GRAPH"], ra)

    # --- isolated pockets: standing spots reachable from NOWHERE (start or any connector) ---
    un2 = stand & ~ra
    lab = np.zeros(un2.shape, dtype=np.int32); nl = 0
    for y0, x0 in zip(*np.nonzero(un2)):
        if lab[y0, x0]:
            continue
        nl += 1; lab[y0, x0] = nl; st = [(y0, x0)]
        while st:
            y, x = st.pop()
            for dy in range(-3, 4):
                for dx in range(-6, 7):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < Hh and 0 <= xx < W and un2[yy, xx] and not lab[yy, xx]:
                        lab[yy, xx] = nl; st.append((yy, xx))
    comps2 = []
    for i in range(1, nl + 1):
        ys, xs = np.nonzero(lab == i)
        own = collections.Counter(owner(int(y), int(x)) for y, x in zip(ys, xs)).most_common(1)[0][0]
        comps2.append((own, len(ys), int(xs.min()) * 8, int(xs.max()) * 8 + 7,
                       int(ys.min()) * 16, int(ys.max()) * 16 + 15))
    comps2.sort(key=lambda t: (t[0], -t[1]))
    print("ISOLATED (unreached from start AND from every connector), components >= 16 spots:")
    for own, n, x0, x1, y0, y1 in comps2:
        if n >= 16:
            print(f"  {own:18s} {n:5d} spots  x {x0}..{x1}  y {y0}..{y1}")
    json.dump(comps2, open(os.environ["GRAPH"] + ".comps.json", "w"))

    # --- shaft climb gaps ---
    for k in act.shafts:
        X, Y, w, h = k.dst
        c0, c1 = X // 8, (X + w) // 8
        ledges = sorted({r for r in range(Y // 16, (Y + h) // 16) for c in range(c0, c1)
                         if is_stand(r, c)})
        def hi(arr):
            rows = [r for r in range((Y + h) // 16, Hh) for c in range(max(0, c0 - 8), min(W, c1 + 8))
                    if arr[r, c]]
            return min(rows) * 16 if rows else None
        low = max(ledges) * 16 if ledges else None
        ha, hs = hi(ra), hi(reach)
        print(f"SHAFT {k.id}: lane x {X}..{X + w - 1} y {Y}..{Y + h - 1}; {len(ledges)} ledge rows "
              f"(lowest y {low}); highest reached spot under the lane (+-64 px): from anywhere {ha}, "
              f"from the start {hs}; climb needed to the lowest ledge (or the mouth): "
              f"{(ha - (low if low is not None else Y + h)) if ha is not None else None} px")
