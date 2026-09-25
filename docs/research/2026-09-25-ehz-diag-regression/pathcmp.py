#!/usr/bin/env python3
"""pathcmp.py ref.json other.json...: in the EHZ band, compare the camera sampled after each
tick-advancing frame, tick by tick; print how many of the 56 samples differ and by how much.
A sample read on a frame that ends mid-tick can catch Camera_X updated and Camera_Y not yet."""
import json, sys
def p(f):
    r = json.load(open(f))["rows"]
    return [(x[4], x[5]) for x in r if x[5] < 1024 and x[2] > 0]
ref = p(sys.argv[1])
for f in sys.argv[2:]:
    o = p(f)
    d = [(i, a, b) for i, (a, b) in enumerate(zip(ref, o)) if a != b]
    mx = max((max(abs(a[0] - b[0]), abs(a[1] - b[1])) for _, a, b in d), default=0)
    print(f"{f.split('/')[-1]:<16} samples {len(o)} vs {len(ref)}; differing {len(d)}, max |d| {mx} px")
