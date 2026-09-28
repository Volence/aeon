#!/bin/bash
# collect_mutants.sh : each mutant's diff, build result, and (code mutants) its identity table
# against the base and its witness run, into results/mutants/.
HERE=$(cd "$(dirname "$0")" && pwd)
R1="$HERE/../2026-09-28-parallax-perband"
R="$HERE/results/mutants"; P=$HOME/pxperf
mkdir -p "$R"
for m in C D K E F G H I J; do
  cp "$P/r2_mut$m/mutant.diff" "$R/mut$m.diff"
  { cat "$P/r2_mut$m/done"; cat "$P/r2_mut$m/crc.txt"; } > "$R/mut${m}_build.txt"
  grep -E '\[Error\]|FIRED|error\(s\)' "$P/r2_mut$m/b_cdebug.log" | cut -c1-400 >> "$R/mut${m}_build.txt"
done
for m in C D K E F; do
  python3 "$R1/cmptable.py" "$P/L_r2_base" "$P/L_r2_mut$m" debug_run debug_diag cdebug_diag \
      cdebug_down cdebug_anchor_right cdebug_anchor_down > "$R/cmp_base_mut$m.txt"
  cp "$P/r2_witness_mut$m.txt" "$R/witness_mut${m}_unextended.txt"
done
echo "finished=1"
