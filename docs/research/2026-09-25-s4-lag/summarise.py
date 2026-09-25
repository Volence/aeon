#!/usr/bin/env python3
"""Print every leg's summary for one run tag. Usage: summarise.py <outdir> <tag>
A leg whose JSON is missing is printed as DID NOT RUN, never skipped."""
import json
import sys
from pathlib import Path

out, tag = Path(sys.argv[1]), sys.argv[2]
LEGS = sys.argv[3].split(",") if len(sys.argv) > 3 else [
    "clipdbg_fly", "clipdbg_run", "clip_run", "dbg_fly", "dbg_run", "rel_run"]
ran = 0
for leg in LEGS:
    p = out / f"{tag}_{leg}.json"
    if not p.exists():
        print(f"== {leg}: DID NOT RUN (no {p.name})")
        continue
    ran += 1
    d = json.loads(p.read_text())
    s, h = d["summary"], d["host"]
    print(f"== {leg} {d['rom']} crc={d['crc']} size={d['size']} mode={d['mode']} "
          f"dirs={d.get('dirs', 'right')} notes={d['notes']}")
    if "motion" in s:
        m = s["motion"]
        print(f"   IN MOTION: {m['video_frames']} video frames, {m['ticks']} ticks, lag {m['lag']} "
              f"({m['lag_pct']}%), {m['frames_per_tick']} frames/tick, camera end {m['cam_end']}")
    if "by_camy512" in s:
        print("   by cam_y/512 (video_frames, lag): " +
              " ".join(f"{k}:{v['video_frames']}/{v['lag']}" for k, v in s["by_camy512"].items()))
    print(f"   stepped={s['frames_stepped']} video_frames={s['sum_dFrame_Counter']} "
          f"ticks={s['sum_dLogic_Tick']} lag={s['lag_frames']} ({s['lag_pct']}%) "
          f"Lag_Frame_Count_delta={s.get('Lag_Frame_Count_delta')} "
          f"cam_x {s['cam_x_start']}->{s['cam_x_end']} (max {s['cam_x_max']})")
    print(f"   host: {h['frames']} frames in {h['wall_s']} s = {h['fps']} fps; "
          f"loadavg {h['loadavg_before']} -> {h['loadavg_after']} at {h['date_utc']}; "
          f"cam_end {h['cam_end']}")
    print("   by cam_x/512 (video_frames, lag): " +
          " ".join(f"{k}:{v['video_frames']}/{v['lag']}" for k, v in s["by_camx512"].items()))
print(f"legs with results: {ran} of {len(LEGS)}")
