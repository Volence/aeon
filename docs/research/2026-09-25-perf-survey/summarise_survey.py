#!/usr/bin/env python3
"""Print every leg of one survey run: motion lag, band splits, and the profile's top rows.
Usage: summarise_survey.py <outdir> <tag> <leg,leg,...> [--top N]
A leg whose JSON is missing prints DID NOT RUN, never zero."""
import argparse
import json
from pathlib import Path

FRAME_CYC = 127840


def window(rows, lo, hi=None):
    """lag/video frames over rows[lo:hi] (the exact-over-a-window rule)."""
    r = rows[lo:hi]
    fc = sum(x[1] for x in r)
    lt = sum(x[2] for x in r)
    return fc, fc - lt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    ap.add_argument("tag")
    ap.add_argument("legs")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--band-y", type=int, default=1024, help="report lag for cam_y < this too")
    ap.add_argument("--window", default="", help="lo,hi rows to report lag over (profile windows)")
    a = ap.parse_args()
    ran = 0
    legs = a.legs.split(",")
    for leg in legs:
        p = Path(a.outdir) / f"{a.tag}_{leg}.json"
        if not p.exists():
            print(f"== {leg}: DID NOT RUN (no {p.name})")
            continue
        ran += 1
        d = json.loads(p.read_text())
        s = d["summary"]
        m = s["motion"]
        rows = d["rows"]
        print(f"== {leg}: {d['rom']} crc={d['crc']} size={d['size']} mode={d['mode']} "
              f"dirs={d['dirs']} load {d['loadavg_start'][0]}->{d['loadavg_end'][0]}")
        print(f"   notes: {d['notes']}")
        print(f"   IN MOTION {m['lag']}/{m['video_frames']} ({m['lag_pct']}%), "
              f"{m['frames_per_tick']} frames/tick, cam end {m['cam_end']}; "
              f"LFC_delta={s.get('Lag_Frame_Count_delta')} whole-leg lag={s['lag_frames']}")
        band = [r for r in rows if r[5] < a.band_y]
        bfc = sum(r[1] for r in band)
        print(f"   cam_y<{a.band_y}: {bfc - sum(r[2] for r in band)}/{bfc}")
        if "rows_before_switch" in d:
            k = d["rows_before_switch"]
            fc, lag = window(rows, 0, k)
            fc2, lag2 = window(rows, k)
            print(f"   before switch {lag}/{fc}; after switch {lag2}/{fc2}")
        if a.window:
            lo, hi = (int(x) for x in a.window.split(","))
            fc, lag = window(rows, lo, hi)
            print(f"   WINDOW rows [{lo},{hi}): lag {lag}/{fc}; cam {rows[lo][4:6]} -> {rows[min(hi, len(rows)) - 1][4:6]}")
        pr = d.get("profile")
        if not pr:
            print("   (no profile)")
            continue
        t = max(pr["ticks"], 1)
        vs = next((r for r in pr["items"] if r.get("name") == "VSync_Wait"), None)
        work = (pr["sampleCycles"] - vs["cyclesTotal"]) / t if vs else float("nan")
        print(f"   PROFILE ticks={pr['ticks']} {pr['sampleCycles'] / t:.0f} cyc/tick, work "
              f"{work:.0f}/tick = {work / FRAME_CYC:.3f} fr/tick; identity remainder "
              f"{pr['identity_remainder']} truncated={pr['truncated']}")
        for r in sorted(pr["items"], key=lambda r: -r["cyclesTotal"])[:a.top]:
            cl = ", ".join(f"{e.get('callerName') or e.get('callerAddr')}:{e['cyclesTotal'] / t:.0f}"
                           for e in r.get("callers", [])[:3])
            print(f"     {(r.get('name') or r['addr'])[:40]:<40} incl {r['cyclesTotal'] / t:>7.0f} "
                  f"self {r['cyclesSelfTotal'] / t:>7.0f} calls {r['callsTotal'] / t:>6.2f}  <- {cl}")
    print(f"legs with results: {ran} of {len(legs)}")


if __name__ == "__main__":
    main()
