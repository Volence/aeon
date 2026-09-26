#!/usr/bin/env python3
"""lagwin — attribute LAG FRAMES to routines, from two runs of the same deterministic leg.

  lagwin.py pick LEG.json [--win-len 3] [--controls 40]
      Reads a DEBUG leg's rows (dLag_Frame_Count per video frame is exact per row), and prints
      the --windows list for run_probe.py: each lag frame L gets a window starting at L-1 (the
      overrunning tick starts before the lag VBlank and may finish after it); overlapping windows
      merge into the earlier one. It adds --controls windows at evenly spaced frames with no lag
      within +-4 frames, marked by being listed after a ';' (run_probe takes the union; report
      re-derives which is which from each window's own Lag_Frame_Count delta, not from this list).
  lagwin.py report WIN.json [--top 25]
      Splits the windows by their measured Lag_Frame_Count delta (>0 = lag window, 0 = control)
      and prints per-TICK inclusive and self cycles of each routine in both sets, ranked by the
      difference. "Per tick" divides by the logic ticks inside each set's windows.

Headless lag counts are deterministic; the re-run's windows are checked against the pick (a
window whose lag differs from the pick's expectation is COUNTED and printed, never hidden).
"""
import json
import sys
from collections import defaultdict

FRAME_CYC = 127840


def pick(path, win_len=3, controls=40):
    h = json.load(open(path))
    rows = h["rows"]
    if rows[0][3] is None:
        raise SystemExit("pick needs a DEBUG leg (per-row Lag_Frame_Count); this one has none")
    lag = [i for i, r in enumerate(rows) if r[3]]
    wins, last = [], -99
    for L in lag:
        s = max(L - 1, 0)
        if s < last + win_len:
            continue
        wins.append(s)
        last = s
    quiet = [i for i in range(5, len(rows) - 5)
             if not any(rows[j][3] for j in range(i - 4, i + 5))]
    step = max(len(quiet) // max(controls, 1), 1)
    ctl = [q for q in quiet[::step]][:controls]
    ctl = [c for c in ctl if all(abs(c - w) >= win_len + 1 for w in wins)]
    print(f"# {len(lag)} lag frames -> {len(wins)} windows; {len(ctl)} control windows", file=sys.stderr)
    print(",".join(str(x) for x in sorted(wins + ctl)))


def report(path, top=25):
    h = json.load(open(path))
    ws = h["windows"]
    sets = {"lag": [w for w in ws if (w["lfc"] or 0) > 0], "ctl": [w for w in ws if (w["lfc"] or 0) == 0]}
    agg = {}
    for k, lst in sets.items():
        incl, slf = defaultdict(float), defaultdict(float)
        ticks = sum(w["ticks"] for w in lst)
        frames = sum(w["frames"] for w in lst)
        lagf = sum(w["lfc"] or 0 for w in lst)
        work = 0
        for w in lst:
            p = w["profile"]
            vs = next((r for r in p["items"] if r.get("name") == "VSync_Wait"), None)
            work += p["sampleCycles"] - (vs["cyclesTotal"] if vs else 0)
            for r in p["items"]:
                n = r.get("name") or r["addr"]
                incl[n] += r["cyclesTotal"]
                slf[n] += r["cyclesSelfTotal"]
        agg[k] = dict(n=len(lst), ticks=ticks, frames=frames, lag=lagf, work=work, incl=incl, slf=slf)
        t = max(ticks, 1)
        print(f"{k}: {len(lst)} windows, {frames} frames, {ticks} ticks, {lagf} lag frames, "
              f"work {work / t:.0f}/tick ({work / t / FRAME_CYC:.3f} fr)")
    L, C = agg["lag"], agg["ctl"]
    lt, ct = max(L["ticks"], 1), max(C["ticks"], 1)
    names = set(L["incl"]) | set(C["incl"])
    rows = sorted(names, key=lambda n: -(L["incl"][n] / lt - C["incl"][n] / ct))
    print(f"{'routine':<36} {'lag incl/t':>10} {'ctl incl/t':>10} {'diff':>8} {'lag self/t':>10} {'ctl self/t':>10}")
    for n in rows[:top]:
        print(f"{str(n)[:36]:<36} {L['incl'][n] / lt:>10.0f} {C['incl'][n] / ct:>10.0f} "
              f"{L['incl'][n] / lt - C['incl'][n] / ct:>8.0f} {L['slf'][n] / lt:>10.0f} {C['slf'][n] / ct:>10.0f}")
    print("top by lag-window SELF per tick:")
    for n in sorted(names, key=lambda n: -L["slf"][n])[:top]:
        print(f"  {str(n)[:36]:<36} self {L['slf'][n] / lt:>8.0f}/tick  incl {L['incl'][n] / lt:>8.0f}/tick")


if __name__ == "__main__":
    cmd, path = sys.argv[1], sys.argv[2]
    kw = {}
    for i, x in enumerate(sys.argv):
        if x == "--win-len":
            kw["win_len"] = int(sys.argv[i + 1])
        if x == "--controls":
            kw["controls"] = int(sys.argv[i + 1])
        if x == "--top":
            kw["top"] = int(sys.argv[i + 1])
    pick(path, **kw) if cmd == "pick" else report(path, **kw)
