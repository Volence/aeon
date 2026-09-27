#!/usr/bin/env python3
"""Per-rectangle budget readout for candidate mega-act clips, off the converted zone trees.

A MEASUREMENT over the converted donor trees (`tools/s2_zone_convert.py` output), through the
same functions the clip bake uses: `collision_pipeline.bake_plane_cell` into an uncapped
`AttrSet` (exactly `tools/clip_act_bake.py`'s per-clip count), and `tile_dedupe.dedupe_tiles`
(the canonical-form dedupe the pool is built from). It is a SEARCH aid for picking rectangles;
the numbers the proposal quotes are re-measured by `tools/clip_act_bake.py bake` on the draft
manifest beside this file, and by `s2_clip_budget.py` where its section-granular specs apply.

    python3 measure_clips.py sweep s2disasm/EHZ --w 2048 --step 256
    python3 measure_clips.py union 's2disasm/EHZ:3072,0,2560,1024' 's2disasm/CPZ:0,0,2560,1536' ...
"""
import argparse
import json
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))
import collision_pipeline as CP                            # noqa: E402
import tile_dedupe                                         # noqa: E402

DONORS = REPO / "games/sonic4/data/donors"
SEC = 256
_trees = {}


class Tree:
    def __init__(self, rel):
        d = DONORS / rel
        self.zm = json.loads((d / "zone.json").read_text())
        gw, gh = self.zm["grid"]["w"], self.zm["grid"]["h"]

        def plane(suffix):
            out = np.zeros((gh * SEC, gw * SEC), dtype=np.uint16)
            for s in self.zm["sections"]:
                raw = (d / f"section_{s['n']}.{suffix}.bin").read_bytes()
                out[s["sy"] * SEC:(s["sy"] + 1) * SEC, s["sx"] * SEC:(s["sx"] + 1) * SEC] = \
                    np.frombuffer(raw, dtype=">u2").reshape(SEC, SEC)
            return out
        self.tiles = plane("tiles")
        self.ca = plane("collattr")
        self.cb = plane("collattrb")
        art = (d / "tileset.bin").read_bytes()
        self.art = [art[i * 32:(i + 1) * 32] for i in range(len(art) // 32)]
        bank = REPO / self.zm["collision"]["base_bank"]
        self.hm = (bank / "heightmaps.bin").read_bytes()
        self.an = (bank / "angles.bin").read_bytes()
        self.crop = self.zm["extent"]["crop_tiles"]


def tree(rel):
    if rel not in _trees:
        _trees[rel] = Tree(rel)
    return _trees[rel]


def words_in(t, x, y, w, h):
    c0, r0, c1, r1 = x // 8, y // 8, (x + w) // 8, (y + h) // 8
    return (t.tiles[r0:r1, c0:c1], t.ca[r0:r1, c0:c1], t.cb[r0:r1, c0:c1])


def attr_into(t, ca, cb, aset):
    for w in np.unique(np.concatenate([ca.ravel(), cb.ravel()])).tolist():
        CP.bake_plane_cell(int(w), t.hm, t.an, aset)


def canon_tiles(t, tl):
    idx = np.unique(tl & 0x7FF).tolist()
    raw = [t.art[i] for i in idx if i < len(t.art)]
    uniq, _ = tile_dedupe.dedupe_tiles(raw)
    return len(uniq)


def parse(spec):
    rel, _, r = spec.partition(":")
    x, y, w, h = (int(v) for v in r.split(","))
    return rel, x, y, w, h


def mode_union(a):
    total = CP.AttrSet(cap=None)
    rows = []
    tiles_total = 0
    for spec in a.specs:
        rel, x, y, w, h = parse(spec)
        t = tree(rel)
        tl, ca, cb = words_in(t, x, y, w, h)
        alone = CP.AttrSet(cap=None)
        attr_into(t, ca, cb, alone)
        before = len(total.entries)
        attr_into(t, ca, cb, total)
        n = canon_tiles(t, tl)
        tiles_total += n
        rows.append((spec, len(alone.entries) - 1, len(total.entries) - before, n,
                     int(((tl & 0x7FF) != 0).sum())))
    for spec, al, ad, n, painted in rows:
        print(f"{spec:44s} attr alone {al:3d}  added {ad:3d}  canonical tiles {n:4d}  "
              f"painted cells {painted}")
    u = len(total.entries) - 1
    print(f"UNION attr entries {u} of 255 -> {'FITS' if u <= 255 else 'OVER by %d' % (u - 255)}; "
          f"sum of per-clip canonical tiles {tiles_total} (the pool keys zones apart, so this "
          f"is the pool before corridor art)")
    return 0 if u <= 255 else 1


def mode_sweep(a):
    t = tree(a.tree)
    x0, x1, y0, y1 = t.crop
    X1, Y1 = x1 * 8, y1 * 8
    hs = a.h or [Y1 - y0 * 8]
    out = []
    for h in hs:
        for y in range(y0 * 8, Y1 - h + 1, a.ystep):
            for x in range(x0 * 8, X1 - a.w + 1, a.step):
                tl, ca, cb = words_in(t, x, y, a.w, h)
                s = CP.AttrSet(cap=None)
                attr_into(t, ca, cb, s)
                out.append((len(s.entries) - 1, x, y, a.w, h, canon_tiles(t, tl)))
    out.sort()
    for r in out[:a.top]:
        print(f"attr {r[0]:3d}  rect x={r[1]} y={r[2]} w={r[3]} h={r[4]}  canonical tiles {r[5]}")
    print(f"... {len(out)} rects; attr min {out[0][0]} median {out[len(out)//2][0]} max {out[-1][0]}")


def mode_search(a):
    """Every combination of one candidate per zone; keep those whose attr union fits `--cap`.

    The union is the set union of each rectangle's interned (heights, angle, solidity) keys,
    which is exactly what one act-wide AttrSet interns (it dedupes on that key)."""
    import itertools
    cands = json.loads(pathlib.Path(a.candidates).read_text())
    keys, area = {}, {}
    for zone, d in cands.items():
        for name, spec in d.items():
            rel, x, y, w, h = parse(spec)
            t = tree(rel)
            _tl, ca, cb = words_in(t, x, y, w, h)
            s = CP.AttrSet(cap=None)
            attr_into(t, ca, cb, s)
            keys[name] = set(s.lookup.keys())
            area[name] = w * h
            print(f"  {name:28s} {len(s.entries) - 1:4d} alone   {spec}")
    res = []
    for combo in itertools.product(*[list(d) for d in cands.values()]):
        u = set().union(*[keys[n] for n in combo])
        res.append((len(u) - 1, sum(area[n] for n in combo), combo))
    ok = sorted((r for r in res if r[0] <= a.cap), key=lambda r: (-r[1], r[0]))
    print(f"{len(res)} combinations, {len(ok)} with a union <= {a.cap}")
    for n, ar, combo in ok[:a.top]:
        print(f"  union {n:3d}  area {ar / 1e6:5.1f} Mpx^2  {' | '.join(combo)}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("search")
    p.add_argument("candidates")
    p.add_argument("--cap", type=int, default=248)
    p.add_argument("--top", type=int, default=20)
    p = sub.add_parser("union")
    p.add_argument("specs", nargs="+")
    p = sub.add_parser("sweep")
    p.add_argument("tree")
    p.add_argument("--w", type=int, default=2048)
    p.add_argument("--h", type=int, nargs="*")
    p.add_argument("--step", type=int, default=512)
    p.add_argument("--ystep", type=int, default=512)
    p.add_argument("--top", type=int, default=8)
    a = ap.parse_args()
    return {"union": mode_union, "sweep": mode_sweep, "search": mode_search}[a.mode](a)


if __name__ == "__main__":
    sys.exit(main())
