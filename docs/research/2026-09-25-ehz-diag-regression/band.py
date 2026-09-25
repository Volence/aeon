#!/usr/bin/env python3
"""band.py <json>... : EHZ band (cam y < 1024) of a diag leg: video frames, ticks, lag,
first/last camera in the band, and a tick-indexed camera path digest (camera at each
logic tick inside the band) so two ROMs' paths can be compared tick for tick."""
import json, sys, hashlib
for f in sys.argv[1:]:
    try:
        d = json.load(open(f))
    except Exception as e:
        print(f, "DID NOT RUN", e); continue
    r = d["rows"]
    band = [x for x in r if x[5] < 1024]
    vf = sum(x[1] for x in band); lt = sum(x[2] for x in band)
    path = [(x[4], x[5]) for x in band if x[2] > 0]   # camera after each tick-advancing frame
    h = hashlib.sha1(repr(path).encode()).hexdigest()[:10]
    m = d["summary"]["motion"]
    print(f"{f.split('/')[-1]:<22} crc={d['crc']} band {len(band)} rows vf={vf} ticks={lt} lag={vf-lt} "
          f"first={band[0][4:6]} last={band[-1][4:6]} path_sha={h} | whole {m['lag']}/{m['video_frames']} "
          f"ticks={m['ticks']} end={m['cam_end']} load={d['loadavg_start'][0]}->{d['loadavg_end'][0]}")
