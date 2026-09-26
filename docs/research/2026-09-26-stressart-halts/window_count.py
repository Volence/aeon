#!/usr/bin/env python3
"""window_count — the STRESS_ART bake's static per-window page count under alternative pin
sets and frame counts (STRESSART-HALTS parcel, 2026-09-26). Evidence, not a gate.

Run from the root of a tree whose generated OJZ act is a STRESS bake (e.g. after
`STRESS_UNIQUIFY=2600 tools/regenerate-level.sh`). Uses tools/fg_page_order.py's own count
(the one build.sh prints as "FG page budget ... worst window needs N"):

    needed(window) = | pins UNION pages referenced by the window's non-blank words |

and reports, for the manifest's pins, for page 0 alone, and for the frame-aware subset of
the manifest's pins (fg_page_order.frame_aware_pins, the rule the canonical bake uses),
the worst window and how many windows exceed F for F in 12..15.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), "tools"))
import numpy as np  # noqa: E402
import fg_page_order as fpo  # noqa: E402


def main():
    c = fpo.load_budget_constants()
    pg, pins, n_pages = fpo.committed_placement(c)
    H, W = pg.shape
    lefts, tops, _, _ = fpo.camera_windows(c, W, H)
    F = c["PAGE_FRAMES"]
    print(f"pool {n_pages} pages; manifest pins {pins}; PAGE_FRAMES {F}")
    needed, needed_pin0 = fpo.window_needed(pg, n_pages, pins, c, lefts, tops)
    fa_pins, fa_needed = fpo.frame_aware_pins(pg, pins, F, needed_pin0, c, lefts, tops)
    for label, arr in (("manifest pins", needed), ("page 0 only", needed_pin0),
                       (f"frame-aware pins {fa_pins}", fa_needed)):
        worst = int(arr.max())
        over = {f: int(np.count_nonzero(arr > f)) for f in range(12, 16)}
        print(f"  {label}: worst window {worst}; windows over F: {over}")
    print("finished=1")


if __name__ == "__main__":
    main()
