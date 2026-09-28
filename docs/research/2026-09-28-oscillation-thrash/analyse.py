#!/usr/bin/env python3
"""analyse.py <leg.json> [lo_tick hi_tick] — decode/re-decode accounting from thrash_probe output.

Reads <leg.json> (ehz_run_probe rows: [i, dFC, dLT, dLag, cx, cy, px, py]) and
<leg.json>.thrash.json (per-frame staging diff). Over the leg (or ticks [lo, hi) relative to the
leg's first tick), prints:
  ticks, video frames, lag;  decodes (sum of staging claims) and per tick;
  RE-DECODES: a claim whose key was already claimed earlier IN THE WHOLE RECORD, with the gap in
  ticks since that key's previous claim (a re-decode is a block the cache decoded, lost from
  staging, and needed again);  distinct keys;  page loads, and page RE-loads of the same page;
  frames where the key diff and the Gen delta disagree (loud, never folded in).
"""
import json
import sys
from collections import Counter


def load(p):
    leg = json.load(open(p))
    th = json.load(open(p + ".thrash.json"))
    return leg, th


def classify(k, r):
    """Where the decoded block lies against the cache window (read after the same frame).
    key = sec_x<<24 | sec_y<<16 | block_index; block (bx, by) covers tile cols bx*16..+15 and
    rows by*16..+15. 'in' = it intersects the window (a demand fill, or speculation the window
    has already reached); otherwise the side(s) of the window it lies beyond (speculation)."""
    sx, sy, bi = k >> 24 & 0xFF, k >> 16 & 0xFF, k & 0xFF
    c0 = (sx * 16 + (bi & 15)) * 16
    r0 = (sy * 16 + (bi >> 4)) * 16
    left, head, top, bot = r[8], r[9], r[10], r[11]
    h = "L" if c0 + 15 < left else ("R" if c0 > head else "")
    v = "U" if r0 + 15 < top else ("D" if r0 > bot else "")
    return (v + h) or "in"


def analyse(p, lo=None, hi=None, quiet=False):
    leg, th = load(p)
    rows = th["rows"]
    # thrash_probe snaps once after every leg frame, plus a few setup snaps before the leg:
    # the leg's frames are therefore exactly the LAST len(leg["rows"]) staging rows.
    nleg = len(leg["rows"])
    legrows = rows[-nleg:]
    first_lt = legrows[0][1]
    seen_at = {}
    for r in rows[: len(rows) - len(legrows)]:
        for k in r[5]:
            seen_at[k] = r[1]
    dec = redec = mism = 0
    gaps = []
    distinct = set()
    page_loads, page_reloads = 0, 0
    pl_seen = Counter()
    per_key = Counter()
    ticks = frames = lag = 0
    burst = Counter()
    where = Counter()   # decode classified against the cache window read the same frame
    where_re = Counter()
    # residency: round-robin eviction is exact, so a claim lives until 16 further claims.
    # A claim is WASTED when the cache window never intersected its block while it lived.
    claims = [(j, k) for j, r in enumerate(legrows) for k in r[5]]
    wasted = Counter()
    for n, (j, k) in enumerate(claims):
        end = claims[n + 16][0] if n + 16 < len(claims) else len(legrows) - 1
        rel = legrows[j][1] - first_lt
        if (lo is not None and rel < lo) or (hi is not None and rel >= hi):
            continue
        if not any(classify(k, legrows[m]) == "in" for m in range(j, end + 1)):
            wasted[classify(k, legrows[j])] += 1
    for r, lr in zip(legrows, leg["rows"]):
        rel = r[1] - first_lt
        inwin = (lo is None or rel >= lo) and (hi is None or rel < hi)
        for k in r[5]:
            if inwin:
                where[classify(k, r)] += 1
                dec += 1
                distinct.add(k)
                per_key[k] += 1
                if k in seen_at:
                    where_re[classify(k, r)] += 1
                    redec += 1
                    gaps.append(r[1] - seen_at[k])
            seen_at[k] = r[1]
        for pg in r[6]:
            if inwin:
                page_loads += 1
                if pl_seen[pg]:
                    page_reloads += 1
            pl_seen[pg] += 1
        if inwin:
            if r[4] != len(r[5]):
                mism += 1
            frames += lr[1]
            ticks += lr[2]
            if lr[2]:
                burst[len(r[5])] += 1
    lag = frames - ticks
    gaps.sort()
    med = gaps[len(gaps) // 2] if gaps else None
    out = dict(leg=p.split("/")[-1], rom=leg["crc"], size=leg["size"], ticks=ticks, frames=frames,
               lag=lag, decodes=dec, per_tick=round(dec / max(ticks, 1), 3), redecodes=redec,
               redecode_pct=round(100 * redec / max(dec, 1), 1), distinct=len(distinct),
               gap_median=med, gap_le16=sum(1 for g in gaps if g <= 16),
               gap_le64=sum(1 for g in gaps if g <= 64),
               top_keys=[("%08x" % k, n) for k, n in per_key.most_common(6)],
               page_loads=page_loads, page_reloads=page_reloads, gen_mismatch_frames=mism,
               decodes_per_frame_hist=dict(sorted(burst.items())), where=dict(where), where_re=dict(where_re),
               wasted=dict(wasted), wasted_total=sum(wasted.values()))
    if not quiet:
        print(json.dumps(out))
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    lo = int(a[1]) if len(a) > 1 else None
    hi = int(a[2]) if len(a) > 2 else None
    analyse(a[0], lo, hi)
