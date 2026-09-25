#!/usr/bin/env python3
"""List where a leg's lag frames fell. Usage: lag_rows.py <leg.json> [x_lo x_hi]
Uses dLag_Frame_Count when the shape has it (exact per frame: +1 in VInt_Lag), else
flags rows with dLogic_Tick == 0 (approximate per row; exact only summed)."""
import json
import sys

d = json.load(open(sys.argv[1]))
lo = int(sys.argv[2]) if len(sys.argv) > 2 else -1
hi = int(sys.argv[3]) if len(sys.argv) > 3 else 1 << 30
rows = d["rows"]
exact = rows and rows[0][3] is not None
lagi = [r for r in rows if (r[3] if exact else (r[2] == 0)) and lo <= r[4] < hi]
print(f"{d['rom']} {d['crc']} mode={d['mode']} basis={'Lag_Frame_Count' if exact else 'dLogic_Tick==0'}"
      f" lag rows in cam_x [{lo},{hi}): {len(lagi)}")
prev = None
gaps = []
for r in lagi:
    if prev is not None:
        gaps.append(r[0] - prev)
    prev = r[0]
print("frame index, cam_x, cam_y, player_x, player_y:")
print(" ".join(f"{r[0]}@({r[4]},{r[5]}|p{r[6]},{r[7]})" for r in lagi))
print("gaps between lag rows (video frames):", gaps)
