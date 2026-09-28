import re
import sys


def syms(p):
    d = {}
    for line in open(p, errors="replace"):
        m = re.match(r"^ (\w+) : (FFFF[0-9A-F]{4}) C \|", line)
        if m:
            d[m.group(1)] = int(m.group(2), 16)
    return d


a, b = syms(sys.argv[1]), sys.argv[2]
b = syms(b)
rows = sorted((a[k], k, b[k] - a[k]) for k in a if k in b and a[k] >= 0xFFFF8000)
prev = None
for addr, k, d in rows:
    if d != prev:
        print(f"{addr:08X} {k} delta {d}")
        prev = d
