"""Deep Forest v15 — marching colonnade (true HCZ-pillar technique).

Band rows BAND_R0..BAND_R1 are a single horizontally-periodic pattern
(128px: one giant organic trunk + featureless dark gap) that the engine
translates 1px at a time: fine sub-tile shift via 8 pre-shifted banks,
whole-tile shift via rotated split DMA — the WHOLE trunk marches, edges
included, unlike v14's texture-crawl-inside-static-silhouette.
"""
import json, zlib, struct, math

LINE2 = [(0,0,0),(36,0,0),(0,0,146),(73,36,36),(146,73,36),(182,109,36),(219,146,73),(255,182,109),
         (0,0,0),(0,36,0),(0,73,36),(0,109,73),(0,182,73),(36,146,73),(109,219,36),(182,255,109)]
PW, H = 256, 512
BLACK, DGRN1, DGRN2, MGRN, BGRN, LGRN, XGRN, XXGRN = 8, 9, 10, 11, 13, 12, 14, 15
DBRN, MBRN, LBRN = 3, 4, 5
RBRN = 1
buf = [[DGRN1]*PW for _ in range(H)]

def P(x,y,c):
    if 0<=y<H: buf[y][x%PW]=c

BAND_R0, BAND_R1 = 8, 39      # animated tile rows (y 64..319)
PAT_W   = 128                 # pattern period px (2 trunks per 256 module)
PAT_ROWS = 4                  # vertical tile period (32px)
BAYER4 = [[0,8,2,10],[12,4,14,6],[3,11,1,9],[15,7,13,5]]

# ============ colonnade pattern (the animated layer) ============
TRUNK_C, TRUNK_W = 64, 44
WAV_L = (0,1,1,2,2,2,1,1,0,0,1,1,2,1,0,0)   # edge waver, 32px vertical period
WAV_R = (2,1,1,0,0,1,1,2,2,2,1,0,0,1,2,2)

def trunk_pixel(ut, yy):
    """Trunk color at trunk-space coord ut (0..127), or None outside the trunk."""
    L = TRUNK_C - TRUNK_W//2 + WAV_L[yy//2]
    R = TRUNK_C + TRUNK_W//2 - WAV_R[yy//2]
    if not (L <= ut <= R): return None
    i = ut - L; w = R - L
    # rim AA + broken rim light (left = lit side)
    if i == 0 or i == w: return DGRN1
    if i == 1: return BLACK
    if i == 2: return DGRN2 if yy % 7 != 3 else BLACK
    if i == w-1 or i == w-2: return BLACK
    # bark: coherent strand zones over a cylinder ramp, lit crest left of center
    ZONES = (DBRN, MBRN, LBRN, LBRN, MBRN, LBRN, MBRN, MBRN,
             DBRN, MBRN, DBRN, DBRN, RBRN, DBRN, RBRN, RBRN)
    waver = (0,0,1,1,2,1,1,0,0,1,2,2,1,0,1,1)[(yy//2) % 16]
    zip_n = (yy + ut*5) % 8 < 2
    s = (i*16)//w + waver + (1 if zip_n else 0)
    c = ZONES[min(15, s)]
    if (s*5 + yy//4) % 11 == 0: c = DBRN if c in (LBRN, MBRN) else BLACK
    if yy in (13, 14) and (ut*7 + yy) % 32 < 11: c = BLACK   # partial crack ring
    if yy in (27, 28) and (ut*5 + 9) % 32 < 9: c = RBRN      # scar band, offset half-period
    return c

def wall_pixel(v, yy):
    """Backdrop forest wall. MUST be 8px-periodic in v: whole-tile DMA
    rotation shifts it by multiples of 8, which must be invisible —
    that is what lets the trunk move while the wall stays put."""
    col = v % 8
    c = (DGRN1, BLACK, DGRN1, DGRN1, DGRN2, DGRN1, BLACK, DGRN1)[col]
    if c == DGRN2 and (yy + col*3) % 16 < 5: c = DGRN1     # broken highlight strand
    if c == BLACK and (yy*3 + col) % 32 < 2: c = DGRN1     # notched shadow strand
    if c == DGRN1 and yy in (7, 23) and col in (2, 3): c = BLACK  # faint cross-shadow
    return c

def pat_pixel(v, y, ph=0):
    """Composite at pattern coord v for fine phase ph: the trunk samples
    shifted space (it translates 1px per step); the wall samples fixed
    space (it only ever moves in invisible 8px jumps)."""
    yy = y % 32
    c = trunk_pixel((v + ph) % PAT_W, yy)
    return c if c is not None else wall_pixel(v, yy)

# ============ static top: haze + canopy ceiling (rows 0..6, y<56) ============
def top_haze(x, y):
    def mix(a, b, frac16):
        return b if BAYER4[y%4][x%4] < frac16 else a
    if y < 28: return DGRN1
    if y < 40: return mix(DGRN1, DGRN2, (y-28)*16//12)
    if y < 48: return DGRN2
    if y < 56: return mix(DGRN2, DGRN1, (y-48)*16//8)  # fade into colonnade shadow
    return DGRN1
for y in range(64):
    for x in range(PW): buf[y][x] = top_haze(x, y)

L1=[8,5,3,1,0,0,1,2,4,6]
for x in range(PW):
    xq=(x//2)*2
    depth = 26 + L1[(xq//16)%8]*2
    for y in range(depth):
        if y < depth-14:
            P(x, y, BLACK)
        else:
            row = y // 5
            sx = (x + (row % 2) * 4) % 8
            sy = y % 5
            arc = (1,2,3,3,2,1,0,0)[sx]
            if sy == arc: c = DGRN2 if y > depth-7 else DGRN1
            elif sy == 4 and sx in (0,7): c = BLACK
            else: c = DGRN1
            P(x, y, c)
    fr = (3, 6, 2, 5)[(x//4) % 4]
    for i in range(fr):
        P(x, depth+i, DGRN1 if i < fr-2 else DGRN2)
    if x % 8 in (1, 6):
        P(x, depth+fr, DGRN2); P(x, depth+fr+1, DGRN1)

def hang_cluster(cx, cy, n, body, lit):
    for k in range(n):
        bx = cx + (k - n//2) * 3
        ln = (8, 13, 10, 12, 9)[k % 5]
        for t in range(ln):
            P(bx + (t//4) * (1 if k % 2 else -1), cy + t, body if t < ln-3 else lit)
hang_cluster(92, 42, 5, DGRN1, DGRN2)
hang_cluster(228, 43, 4, DGRN1, DGRN2)
def vine(x, y0, ln, c1, c2, leaf_at=()):
    cx=x
    for i in range(ln):
        if i in (8,16): cx+=1
        P(cx, y0+i, c1 if i%3 else c2)
        if i in leaf_at:
            for d in (-2,-1,1,2): P(cx+d, y0+i+(abs(d)==2), c2)
            P(cx, y0+i+1, c1)
for x, ln in ((36,26),(108,30),(164,30),(228,24)):
    vine(x, 24, ln, DGRN1, DGRN2, leaf_at=(14, 24))
def moss_strand(x, y0, ln):
    for i in range(ln):
        a = DGRN1 if (i//3) % 2 else DGRN2
        b = DGRN2 if (i//3) % 2 else DGRN1
        P(x, y0+i, a)
        if i % 2: P(x+1, y0+i, b)
moss_strand(232, 30, 24)

# ============ static bottom: undergrowth (rows 40..47, y320..383) ============
UND = 320                       # top of the undergrowth region
for y in range(UND, UND+64):
    for x in range(PW): buf[y][x] = DGRN1
for x in range(PW):
    xq=(x//2)*2
    h1 = 50 + L1[(xq//8)%8]*3 + L1[(xq//16+2)%8]
    for i in range(h1):
        y = UND+63-i
        if y >= UND: P(x, y, DGRN1 if i > h1-10 else BLACK)

def under_mass(y_top_fn, body, lit, lit_density=3, style='scale'):
    for x in range(PW):
        yt = y_top_fn(x)
        if style == 'strands':
            hvar = (0, 2, 1, 3)[(x//4) % 4]
            for y in range(yt + hvar, UND+64):
                zip_n = (y + x*5) % 16 < 3
                sid = x + (1 if zip_n else 0)
                c = (body, lit, body, body, lit, DGRN2, body, lit)[sid % 8]
                if y < yt + hvar + 2 and sid % 3 == 0: c = LGRN
                elif y < yt + hvar + 1: c = lit
                P(x, y, c)
            continue
        for y in range(yt, UND+64):
            row = y // 5
            sx = (x + (row % 2) * 4) % 8
            sy = y % 5
            deep = (y - yt) // 10
            lt = lit if deep < 2 else body
            arc = (1,2,3,3,2,1,0,0)[sx]
            if sy == arc: c = lt
            elif sy == arc+1 and sx in (2,3,4): c = body
            elif sy == 4 and sx in (0,7): c = BLACK
            else: c = body
            P(x, y, c)
        if (x + yt) % 4 != 0:
            P(x, yt, lit)
            if x % 4 == 1: P(x, yt+1, lit)
        elif x % 2: P(x, yt-1, body)
        if lit_density == 3 and x % 8 in (0,1,2,5,6): P(x, yt-1, DGRN2)
        sp = x % 16
        if sp == 4 or sp == 12:
            h0 = yt - 1
            P(x, h0, body); P(x, h0-1, body)
            P(x-1, h0-2, lit if sp==4 else body); P(x+1, h0-2, body)
            P(x-1, h0-3, body); P(x+1, h0-3, lit)
            if sp == 12: P(x, h0-2, lit)

L2pat=[0,4,7,9,7,5,2,1,3,6]
HUMP1 = (6, 2, 0, 0, 1, 4, 7, 8)
def top1(x):
    xq = (x//8)*8
    return UND+4 + HUMP1[((xq + 32)//8) % 8]
HUMP = (7, 3, 1, 0, 0, 1, 3, 7)
def top2(x):
    xq = (x//4)*4
    mound = HUMP[(xq//4) % 8]
    stagger = (3 if (xq//32) % 2 else 0)
    return UND+20 + mound + stagger
def top3(x):
    xq=(x//2)*2
    return UND+42 + L2pat[(xq//8+2)%8]//2

under_mass(top1, BLACK, DGRN1, 3)
under_mass(top2, DGRN1, DGRN2, 2)
for x in range(PW):
    ph = (x//4) % 8
    yt = top2(x)
    if ph in (3, 4):
        if x % 2: P(x, yt, MGRN)
        P(x, yt+1, DGRN2)
    if ph == 0 and (x//4) % 2 == 0:
        for dy in range(6):
            P(x, yt+dy, BLACK if dy < 4 else DGRN1)
def fern(cx, cy, c1, c2):
    for k in range(5):
        a = (-1.3,-0.6,0.0,0.6,1.3)[k]
        ln = (9,12,14,12,9)[k]
        for t in range(ln):
            x = int(cx + t*a); y = cy - t + abs(int(t*a))//3
            if y >= UND:
                P(x, y, c2 if t > ln-4 else c1)
                if t%3==0: P(x-1 if a<0 else x+1, y, c1)
def frond(cx, cy, ln, side, body, lit):
    for t in range(ln):
        x = cx + side * (t * 2 // 3)
        y = cy - t + (t*t)//(ln*2)
        if y < UND: continue
        P(x, y, body)
        if t % 3 == 1 and t > 2:
            for l in range(1, 4 + t//6):
                P(x - l, y + l//2, body if l < 3 else lit)
                P(x + l, y + l//2 - (1 if side > 0 else 0), body)
frond(44, UND+20, 16, 1, MGRN, BGRN)
frond(48, UND+22, 12, -1, DGRN2, MGRN)
frond(172, UND+22, 15, -1, MGRN, BGRN)
frond(168, UND+24, 12, 1, DGRN2, MGRN)
for cx in range(24, PW, 64):
    fern(cx, top2(cx)+4, DGRN2, MGRN)
under_mass(top3, DGRN2, MGRN, 2, style='strands')
for x in range(PW):
    bed = 7 + L2pat[((x//8))%8]//3 + (0,1,0,2)[(x//2)%4]
    for i in range(bed):
        y = UND+63-i
        zip_n = (y + x*3) % 16 < 3
        sid = x + (1 if zip_n else 0)
        c = (MGRN, BGRN, MGRN, DGRN2, BGRN, MGRN, BGRN, MGRN)[sid % 8]
        if i == bed-1: c = (LGRN, XGRN, BGRN, LGRN)[(x//2) % 4]
        P(x, y, c)
def tuft_grass(cx, base_y, n, lean, tones):
    heights = (4, 9, 13, 7, 11)
    for b in range(n):
        bx = cx + (0, 2, 4, 5, 7)[b % 5]
        h = heights[b % 5]
        bend = 1 if b % 2 else -1
        for t in range(h):
            x = bx + (bend if t >= h-2 and h > 6 else 0)
            y = base_y - t
            c = tones[2] if (t == h-1 and h > 8) else (tones[1] if t >= h//2 else tones[0])
            P(x, y, c)
for k, cx in enumerate(range(0, PW, 32)):
    tuft_grass(cx, UND+62, 4+(k%2), 0, (MGRN, BGRN, LGRN))
for cx in range(8, PW, 64):
    fern(cx, UND+60, MGRN, LGRN)

# ============ roots + the dark below (rows 48..63, y384..511) ============
# Wrap design: this region fades to pure black, and row 0 (canopy ceiling)
# is pure black too, so the 512px plane tiles vertically with no seam —
# descending forever just reveals another forest layer below.
# Rows 48..55 are ANIMATED band 2: a timer-driven firefly drift over a
# period-8 root curtain (same composite rule as the colonnade: the curtain
# is invariant under 8px rotation, only the fireflies translate + pulse).
for y in range(384, 512):
    for x in range(PW): buf[y][x] = BLACK
for y in range(376, 384):                     # soil shadow at undergrowth base
    for x in range(PW):
        if BAYER4[y%4][x%4] < (384-y)*16//8: buf[y][x] = BLACK

FF_R0, FF_R1 = 48, 55                          # firefly band tile rows
# fireflies: (u, yy, blink_offset) in 128x32 pattern space
FIREFLIES = [(20, 12, 0), (76, 25, 3), (108, 5, 5), (52, 30, 6), (124, 18, 2)]
FF_CENTER = (None, MGRN, LGRN, XXGRN)          # pulse levels 0..3 (0 = off)
FF_HALO   = (None, None, DGRN2, MGRN)
FF_TRI    = (0, 1, 2, 3, 3, 2, 1, 0)           # triangle pulse over 8 fine phases

def roots_curtain(v, yy):
    """Period-8 root curtain — MUST be invariant under 8px shifts."""
    col = v % 8
    if col == 2 and (yy*3 + 1) % 16 > 3: return DGRN1   # root strand, notched
    if col == 6 and yy % 8 < 5: return DGRN1
    if col == 4 and (yy + 2) % 16 < 2: return DGRN2     # rare glint
    return BLACK

def firefly_at(ut, yy, ph):
    for fu, fy, bo in FIREFLIES:
        lvl = FF_TRI[(ph + bo) % 8]
        if lvl == 0: continue
        du = (ut - fu) % PAT_W
        if du > 64: du -= PAT_W
        dy = yy - fy
        if du == 0 and dy == 0: return FF_CENTER[lvl]
        if abs(du) <= 1 and abs(dy) <= 1 and FF_HALO[lvl] is not None:
            return FF_HALO[lvl]
    return None

def ff_pixel(v, y, ph=0):
    """Firefly band composite: fireflies translate/pulse, curtain stays."""
    yy = y % 32
    c = firefly_at((v + ph) % PAT_W, yy, ph)
    return c if c is not None else roots_curtain(v, yy)

# ============ fill band rows in buf (phase 0, for preview + editor) ============
for y in range(BAND_R0*8, (BAND_R1+1)*8):
    for x in range(PW):
        buf[y][x] = pat_pixel(x % PAT_W, y)
for y in range(FF_R0*8, (FF_R1+1)*8):
    for x in range(PW):
        buf[y][x] = ff_pixel(x % PAT_W, y)

# ============ slice: anim slots first (NO dedup), then static (dedup) ============
def pat_tile(col, vrow, shift):
    """One 8x8 tile of the pattern at fine phase `shift` (column-major slot)."""
    out = []
    for ry in range(8):
        for px in range(8):
            out.append(pat_pixel(col*8 + px, vrow*8 + ry, shift) & 0xF)
    return out

def ff_tile(col, vrow, shift):
    out = []
    for ry in range(8):
        for px in range(8):
            out.append(ff_pixel(col*8 + px, vrow*8 + ry, shift) & 0xF)
    return out

tiles = []
for col in range(16):                 # column-major: each col's 4 tiles contiguous
    for vrow in range(PAT_ROWS):
        tiles.append(pat_tile(col, vrow, 0))
for col in range(16):                 # firefly band: slots 64..127
    for vrow in range(PAT_ROWS):
        tiles.append(ff_tile(col, vrow, 0))
N_ANIM = len(tiles)                   # 128

index = {}                            # static dedup only — never alias anim slots
layout = [0]*4096
for trow in range(64):
    for tcol in range(64):
        if BAND_R0 <= trow <= BAND_R1:
            slot = (tcol % 16) * PAT_ROWS + (trow % PAT_ROWS)
            layout[trow*64+tcol] = slot | (2<<13)
            continue
        if FF_R0 <= trow <= FF_R1:
            slot = 64 + (tcol % 16) * PAT_ROWS + (trow % PAT_ROWS)
            layout[trow*64+tcol] = slot | (2<<13)
            continue
        t=[]
        for y in range(8):
            for x in range(8): t.append(buf[trow*8+y][(tcol*8+x)%PW])
        k=bytes(t)
        if k not in index: index[k]=len(tiles); tiles.append(t)
        layout[trow*64+tcol]=index[k]|(2<<13)
print(f'tiles: {len(tiles)} total ({N_ANIM} animated + {len(tiles)-N_ANIM} static)')

# phase banks: 1px shifts (8 fine phases; whole-tile shifts are DMA rotation)
phases = []
ff_phases = []
for ph in range(8):
    bank, ff_bank = [], []
    for col in range(16):
        for vrow in range(PAT_ROWS):
            bank.append(pat_tile(col, vrow, ph))
            ff_bank.append(ff_tile(col, vrow, ph))
    phases.append(bank)
    ff_phases.append(ff_bank)

# preview PNG
rows=[]
for y in range(H):
    row=bytearray([0])
    for x in range(512):
        r,g,b=LINE2[buf[y][x%PW]]; row+=bytes((r,g,b))
    rows.append(bytes(row))
raw=zlib.compress(b''.join(rows))
def chunk(t,d): return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d))
with open('/tmp/bg_colonnade.png','wb') as f:
    f.write(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',512,H,8,2,0,0,0))+chunk(b'IDAT',raw)+chunk(b'IEND',b''))

import os
OUT = os.environ.get('BG_OUT', os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'editor_bg_override.json'))
json.dump({"layout":layout,"tiles":tiles,
           "anims":[
             {"cols":16,"rows":PAT_ROWS,"pattern_px":PAT_W,
              "driver":"camera_x","rate_shift":2,"slot_base":0,"phases":phases},
             {"cols":16,"rows":PAT_ROWS,"pattern_px":PAT_W,
              "driver":"timer","rate_shift":3,"slot_base":64,"phases":ff_phases},
           ]},
          open(OUT,'w'))
print('dumped', OUT)
