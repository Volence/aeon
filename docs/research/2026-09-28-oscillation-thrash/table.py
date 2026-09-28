#!/usr/bin/env python3
"""table.py <outdir> [<outdir2>] — one row per leg: lag, decodes/tick, re-decode share, pages.

With two dirs (before, after) the legs are cut to the SAME tick span (the smaller tick count,
the 2026-09-27 spancmp rule) and printed side by side. A leg missing from a dir prints
DID NOT RUN. The leg's camera range over the span is printed so a reader can see whether the
camera oscillated.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyse import analyse  # noqa: E402

LEGS = ["c_fly_right", "c_fly_down", "c_run", "c_run_dbg", "c_osc_h4", "c_osc_h8", "c_osc_d4",
        "e_fly_right", "e_run", "e_run_dbg", "e_deadend_dbg", "e_pit", "e_pit_dbg",
        "e_osc_h4", "e_osc_d4"]


def cov(p):
    j = json.load(open(p))
    cv = j.get("coverage") or []
    return [max(r[k] for r in cv) for k in (1, 2, 3, 4)] if cv else None


def ticks_of(p):
    return analyse(p, quiet=True)["ticks"]


def camrange(p, hi):
    th = json.load(open(p + ".thrash.json"))["rows"]
    n = len(json.load(open(p))["rows"])
    rows = th[-n:]
    f = rows[0][1]
    rr = [r for r in rows if r[1] - f < hi]
    return (min(r[2] for r in rr), max(r[2] for r in rr), min(r[3] for r in rr), max(r[3] for r in rr))


def fmt(o):
    return (f"{o['lag']:>3}/{o['frames']:<5} dec {o['decodes']:>4} ({o['per_tick']:.3f}/t) "
            f"re {o['redecode_pct']:>5}% pages {o['page_loads']}/{o['page_reloads']}")


def main():
    dirs = sys.argv[1:]
    for leg in LEGS:
        ps = [os.path.join(d, leg + ".json") for d in dirs]
        have = [os.path.exists(p) and os.path.exists(p + ".thrash.json") for p in ps]
        if not all(have):
            print(f"{leg:<14} " + " | ".join(("ok" if h else "DID NOT RUN") for h in have))
            continue
        span = min(ticks_of(p) for p in ps)
        outs = [analyse(p, 0, span, quiet=True) for p in ps]
        cr = camrange(ps[0], span)
        line = f"{leg:<14} ticks {span:>5} cam x {cr[0]}..{cr[1]} y {cr[2]}..{cr[3]}"
        print(line)
        for d, p, o in zip(dirs, ps, outs):
            print(f"    {os.path.basename(d.rstrip('/')):<10} {o['rom']} {fmt(o)} cov {cov(p)}")


if __name__ == "__main__":
    main()
