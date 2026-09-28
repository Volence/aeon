#!/usr/bin/env python3
"""measure_famine_reach.py — RESEARCH-ONLY measurement for P1-FAMINE-PINNED-CAPACITY.

NOT A GATE. Nothing wires this, nothing grades a build with it, and its exit code is only
"measured (0)" or "could not measure (2)". It answers one question for the research note
docs/research/2026-09-28-p1-famine-reach.md: does the pinned-capacity famine the
STRESS_EVICT fixture hits reach any real act?

It reuses the repo's own count, it does not re-implement it:
  * fg_page_order.window_needed  -> needed = |ALL pins UNION window pages| (the bake's N1)
                                    and needed_pin0 = |{0} UNION window pages| (a pinned page
                                    counted only where the window itself names it)
  * fg_page_order.camera_windows / page_presence_sums  -> the window population
  * clip_act_bake.page_grid_from_tree -> a baked clip tree's page grid and pins (N2's decoder)
  * fg_page_order.committed_placement -> the committed OJZ act 1 grid and pins

Per act it reports, at frame budgets F = 12 (PAGE_FRAMES), 11, 10, 9 (STRESS_EVICT_FRAMES):
  over(F)      windows with needed > F           (all pins resident: the worst case)
  over0(F)     windows with needed_pin0 > F      (only pins the window names: the best case)
and the TRANSIENT unions (a fill mid-step holds part of the old window and part of the
new one): the same count over (COLS+1) x ROWS, COLS x (ROWS+2) and (COLS+1) x (ROWS+2)
windows at the same (left, top) population, with all pins resident.

CONTROL: the OJZ act at F = 9 must report over windows, including the booked famine
window (camera 1376, 144 -> the window at tile left 1376/8 - MARGIN_H). If it does not,
this script is not measuring the thing the booking measured, and it says so (exit 2).

Usage:
  python3 measure_famine_reach.py <baked clip dir>... [--ojz] [--json]
"""

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import fg_page_order as fpo          # noqa: E402
import clip_act_bake as cab          # noqa: E402

BUDGETS = (12, 11, 10, 9)
TOP_N = 5


def cam_of(c, left, top):
    """The camera the bake's own verdict names for a window (budget_verdict's formula)."""
    return ((left + c["TILE_CACHE_MARGIN_H"]) * 8 if left else 0,
            (top + c["TILE_CACHE_MARGIN_V"]) * 8 if top else 0)


def needed_for(pg, n_pages, pins, c, lefts, tops, cols, rows):
    pins = set(pins) | {0}
    sums = fpo.page_presence_sums(pg, lefts, tops, cols, rows,
                                  {"unpinned": set(range(n_pages)) - pins})
    return sums["unpinned"].astype(np.int32) + len(pins)


def worst_windows(needed, lefts, tops, c, n=TOP_N):
    peak = int(needed.max())
    ti, li = np.nonzero(needed == peak)
    out = []
    for t, l in list(zip(ti.tolist(), li.tolist()))[:n]:
        L, T = int(lefts[l]), int(tops[t])
        out.append({"left": L, "top": T, "camera": cam_of(c, L, T)})
    return peak, int(len(ti)), out


def measure(label, pg, pins, n_pages, c):
    H, W = pg.shape
    lefts, tops, _, _ = fpo.camera_windows(c, W, H)
    cols, rows = c["TILE_CACHE_COLS"], c["TILE_CACHE_ROWS"]
    needed, needed_pin0 = fpo.window_needed(pg, n_pages, pins, c, lefts, tops)
    if needed.size == 0:
        raise fpo.BudgetError(f"{label}: no windows — UNMEASURABLE")
    peak, at_peak, worst = worst_windows(needed, lefts, tops, c)
    r = {
        "act": label, "pages": int(n_pages), "pins": sorted(int(p) for p in pins),
        "streaming": bool(n_pages > c["PAGE_FRAMES"]),
        "windows": int(needed.size), "worst": peak, "windows_at_worst": at_peak,
        "worst_windows": worst,
        "worst_pin0": int(needed_pin0.max()),
        "pessimism_windows": int(np.count_nonzero(needed != needed_pin0)),
        "pessimism_max": int((needed - needed_pin0).max()),
        "over": {F: int(np.count_nonzero(needed > F)) for F in BUDGETS},
        "over_pin0": {F: int(np.count_nonzero(needed_pin0 > F)) for F in BUDGETS},
        "transient": {},
    }
    for name, (cc, rr) in {"+1col": (cols + 1, rows), "+2row": (cols, rows + 2),
                           "+1col+2row": (cols + 1, rows + 2)}.items():
        nt = needed_for(pg, n_pages, pins, c, lefts, tops, cc, rr)
        tp, tat, tw = worst_windows(nt, lefts, tops, c)
        r["transient"][name] = {"worst": tp, "at_worst": tat,
                                "over12": int(np.count_nonzero(nt > c["PAGE_FRAMES"])),
                                "worst_windows": tw if tp > c["PAGE_FRAMES"] else []}
    return r, needed, lefts, tops


def main(argv):
    as_json = "--json" in argv
    dirs = [a for a in argv if not a.startswith("--")]
    c = fpo.load_budget_constants()
    if c["PAGE_FRAMES"] != 12:
        print(f"UNMEASURABLE: PAGE_FRAMES is {c['PAGE_FRAMES']}, this note's budgets assume 12")
        return 2
    results = []
    if "--ojz" in argv:
        pg, pins, n = fpo.committed_placement(c)
        r, needed, lefts, tops = measure("ojz/act1 (committed)", pg, pins, n, c)
        # CONTROL: the booked famine window must be over at F = 9.
        L = 1376 // 8 - c["TILE_CACHE_MARGIN_H"]
        T = max(0, 144 // 8 - c["TILE_CACHE_MARGIN_V"]) & ~1
        li = np.searchsorted(lefts, L)
        ti = np.searchsorted(tops, T)
        if li >= len(lefts) or lefts[li] != L or ti >= len(tops) or tops[ti] != T:
            print(f"UNMEASURABLE: control window (left {L}, top {T}) is not in the population")
            return 2
        got = int(needed[ti, li])
        r["control"] = {"camera": (1376, 144), "left": L, "top": T, "needed": got,
                        "over_at_9": got > 9}
        if got <= 9:
            print(f"UNMEASURABLE: CONTROL FAILED — the booked famine window needs {got} <= 9 "
                  f"here; this script is not measuring what the booking measured")
            return 2
        results.append(r)
    for d in dirs:
        pg, pins, n = cab.page_grid_from_tree(d)
        r, *_ = measure(os.path.basename(os.path.normpath(d)), pg, pins, n, c)
        results.append(r)
    if not results:
        print(__doc__)
        return 2
    if as_json:
        print(json.dumps(results, indent=1))
        return 0
    for r in results:
        w = r["worst_windows"][0]
        print(f"{r['act']}: {r['pages']} pages ({'STREAMING' if r['streaming'] else 'fully resident'}), "
              f"pins {r['pins']}; {r['windows']} windows; worst {r['worst']} "
              f"({r['windows_at_worst']} at worst, first camera {w['camera']}); "
              f"worst with pins-only-where-named {r['worst_pin0']} "
              f"(differs in {r['pessimism_windows']} windows, by <= {r['pessimism_max']})")
        print(f"    over F (all pins): {r['over']}   over F (pins where named): {r['over_pin0']}")
        for k, v in r["transient"].items():
            print(f"    transient {k}: worst {v['worst']}, {v['over12']} over 12"
                  + (f", e.g. {v['worst_windows'][:3]}" if v["worst_windows"] else ""))
        if "control" in r:
            print(f"    CONTROL: booked famine window camera {r['control']['camera']} needs "
                  f"{r['control']['needed']} (> 9: {r['control']['over_at_9']})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (fpo.BudgetError, cab.ClipBakeError, OSError) as exc:
        print(f"UNMEASURABLE: {exc}")
        sys.exit(2)
