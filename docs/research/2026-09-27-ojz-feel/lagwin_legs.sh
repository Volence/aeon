#!/bin/bash
# lagwin_legs.sh <rom-stem> <legsdir> LEG...: re-run each named leg of <legsdir> (same script)
# with a profiler window around every lag frame plus quiet controls (the EHZ parcel's
# lagwin.py pick rule), writing <legsdir>/LEG_win.json. Deterministic re-run: the lag frames
# are the pick's, and each window's own Lag_Frame_Count says which it is.
HERE=$(cd "$(dirname "$0")" && pwd)
R=$1; LD=$2; shift 2
export TMPDIR=/home/volence/.cache/aeon-tmp
for leg in "$@"; do
  sc=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['script'])" "$LD/$leg.json")
  w=$(python3 "$HERE/../2026-09-27-ehz-run-lag/lagwin.py" pick "$LD/$leg.json" --controls 10)
  timeout 1200 python3 "$HERE/ojz_feel_probe.py" --rom "$R.bin" --lst "$R.lst" --script "$sc" \
      --windows "$w" --out "$LD/${leg}_win.json" > "$LD/${leg}_win.txt" 2>&1
  echo "$leg rc=$?"
done
