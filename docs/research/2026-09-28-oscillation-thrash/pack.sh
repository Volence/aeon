#!/bin/bash
# pack.sh <workdir> <tag> [<base tag>] : copy one run's CRCs, legs.meta and leg JSONs (tar.gz) into
#   results/, and write table_<tag>.txt (or table_<base>_vs_<tag>.txt with a base).
#   <workdir> holds roms/<tag>/crc.txt and out/<tag>/ (as .perf/ does in the parcel's worktree).
HERE=$(cd "$(dirname "$0")" && pwd)
W=$1; T=$2; B=$3
R="$HERE/results"; mkdir -p "$R"
cp "$W/roms/$T/crc.txt" "$R/crc_$T.txt"
cp "$W/out/$T/legs.meta" "$R/legs_$T.meta"
tar -czf "$R/legs_$T.tar.gz" -C "$W/out" "$T"
if [ -n "$B" ]; then
  python3 "$HERE/table.py" "$W/out/$B" "$W/out/$T" > "$R/table_${B}_vs_$T.txt"
else
  python3 "$HERE/table.py" "$W/out/$T" > "$R/table_$T.txt"
fi
