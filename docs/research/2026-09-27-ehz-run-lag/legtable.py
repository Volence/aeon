#!/usr/bin/env python3
"""legtable — the lag table for one or more run_legs.sh output dirs, plus path identity.

usage: legtable.py DIR [DIR2]
For each leg: lag / video frames in motion, ticks, end position, lag per 1024 px of player x.
With DIR2: the tick-indexed player path of each leg is compared between the two dirs (same
tick -> same player x,y). A leg whose paths differ is printed as PATH DIFFERS with the first
differing tick, so its lag comparison is flagged rather than trusted. diag legs compare the EHZ
band (camera y < 1024) and the band's camera path digest (docs/research/2026-09-25-ehz-diag-
regression/band.py's rule).
"""
import hashlib
import json
import os
import sys


def load(d, name):
    p = os.path.join(d, name + ".json")
    return json.load(open(p)) if os.path.exists(p) else None


def run_row(h):
    m = h["summary"]["motion"]
    b = {}
    for r in h["rows"]:
        e = b.setdefault(r[6] // 1024 * 1024, [0, 0])
        e[0] += r[1]
        e[1] += r[2]
    by = " ".join(f"{k}:{v[0] - v[1]}" for k, v in sorted(b.items()))
    return (f"lag {m['lag']:>3}/{m['video_frames']:<5} ticks {m['ticks']:<5} crc {h['crc']} "
            f"end {h['rows'][-1][6:8]} | lag per 1024px of player x: {by}")


def diag_row(h):
    r = h["rows"]
    band = [x for x in r if x[5] < 1024]
    vf = sum(x[1] for x in band)
    lt = sum(x[2] for x in band)
    path = [(x[4], x[5]) for x in band if x[2] > 0]
    m = h["summary"]["motion"]
    return (f"EHZ band lag {vf - lt}/{vf} ticks {lt} path_sha "
            f"{hashlib.sha1(repr(path).encode()).hexdigest()[:10]} | whole {m['lag']}/{m['video_frames']} "
            f"crc {h['crc']}"), path


def main():
    dirs = sys.argv[1:]
    legs = ["plain_run", "plain_spin", "debug_run", "debug_spin", "debug_diag"]
    for leg in legs:
        hs = [load(d, leg) for d in dirs]
        for d, h in zip(dirs, hs):
            if h is None:
                print(f"{leg:<11} {os.path.basename(d.rstrip('/')):<12} DID NOT RUN")
                continue
            row = diag_row(h)[0] if leg.endswith("diag") else run_row(h)
            print(f"{leg:<11} {os.path.basename(d.rstrip('/')):<12} {row}")
        if len(hs) == 2 and all(hs):
            a, b = hs
            if leg.endswith("diag"):
                same = diag_row(a)[1] == diag_row(b)[1]
                print(f"{'':<11} path: {'SAME band camera path' if same else 'PATH DIFFERS (band)'}")
            else:
                pa, pb = a["path"], b["path"]
                common = sorted(set(pa) & set(pb), key=int)
                diff = [t for t in common if pa[t][:2] != pb[t][:2]]
                print(f"{'':<11} path: {len(common)} common ticks, "
                      + (f"PATH DIFFERS first at tick {diff[0]} ({pa[diff[0]][:2]} vs {pb[diff[0]][:2]}), "
                         f"{len(diff)} ticks differ" if diff else "player path IDENTICAL at every common tick"))


if __name__ == "__main__":
    main()
