#!/usr/bin/env python3
"""gpl_summary — one table row per (ROM tag, leg) from gpl_legs.sh's .json files.

Lag over a window = sum(dFrame_Counter) - sum(dLogic_Tick) (the survey's exact rule).
Windows reported, all in video frames while the camera moves ("motion", leg_probe's own):
  * motion       — the whole leg in motion (leg_probe's summary, re-derived here)
  * before/after — split at the two-phase switch (cpz legs only)
  * band         — CPZ legs: after the switch, camera y < 2048 (Chemical Plant's painted
                   rows the survey's 30/150 window covered, y 160 -> ~2032);
                   EHZ diagonal: camera y < 1024 (the survey's "EHZ band")
  * PatchRun_Seq — profiled legs only: incl cycles per tick and per call over the
                   profiled window
A missing .json prints DID NOT RUN, never a zero.
Usage: gpl_summary.py <dir> <tag>[,<tag>...] <leg>[,<leg>...]
"""
import json
import sys
from pathlib import Path


def lag(rows):
    return sum(r[1] for r in rows) - sum(r[2] for r in rows), sum(r[1] for r in rows)


def motion_rows(rows):
    n = len(rows)
    last = max((i for i in range(1, n) if rows[i][4:6] != rows[i - 1][4:6]), default=n - 1)
    return rows[:last + 1]


def fmt(p):
    return f"{p[0]}/{p[1]}"


def main():
    d, tags, legs = Path(sys.argv[1]), sys.argv[2].split(","), sys.argv[3].split(",")
    print(f"{'tag':<14} {'leg':<10} {'crc':<9} {'motion':>9} {'before':>9} {'after':>9} {'band':>9} "
          f"{'cam_end':>13} {'DM_end':>6} {'Seq/tick':>9} {'Seq/call':>9} {'calls/t':>7}")
    for t in tags:
        for leg in legs:
            f = d / f"{t}_{leg}.json"
            if not f.exists():
                print(f"{t:<14} {leg:<10} DID NOT RUN ({f.name} missing)")
                continue
            h = json.loads(f.read_text())
            rows = motion_rows(h["rows"])
            m = lag(rows)
            k = h.get("rows_before_switch")
            before = after = band = None
            base = leg.rstrip("P")
            if k is not None:
                before, after = lag(rows[:k]), lag(rows[k:])
                band = lag([r for r in rows[k:] if r[5] < 2048])
            elif base == "diag":
                band = lag([r for r in rows if r[5] < 1024])
            dm = (h.get("read_at_end") or {}).get("PageCache_Direct_Map", "")
            seq = ("", "", "")
            p = h.get("profile")
            if p:
                it = next((r for r in p["items"] if r.get("name") == "PageCache_PatchRun_Seq"), None)
                tk = max(p["ticks"], 1)
                if it:
                    seq = (f"{it['cyclesTotal'] / tk:.0f}", f"{it['cyclesTotal'] / max(it['callsTotal'], 1):.0f}",
                           f"{it['callsTotal'] / tk:.2f}")
            print(f"{t:<14} {leg:<10} {h['crc']:<9} {fmt(m):>9} {fmt(before) if before else '-':>9} "
                  f"{fmt(after) if after else '-':>9} {fmt(band) if band else '-':>9} "
                  f"{str(rows[-1][4:6]):>13} {str(dm):>6} {seq[0]:>9} {seq[1]:>9} {seq[2]:>7}")


if __name__ == "__main__":
    main()
