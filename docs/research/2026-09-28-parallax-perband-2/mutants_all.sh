#!/bin/bash
# mutants_all.sh : build_mutant2.sh for every mutant in turn (tags r2_mut<X>), then, for the
# five code mutants, the identity legs against the base (legs.sh into $HOME/pxperf/L_r2_mut<X>)
# and the Step 4a key witness on the canonical DEBUG ROM. The log's last line is
# finished=<mutants built>.
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(cd "$HERE/../../.." && pwd)
LEGS="$HERE/../2026-09-28-parallax-perband/legs.sh"
LOG=$HOME/pxperf/r2_mut_build.log
n=0
for m in C D K E F G H I J; do
  "$HERE/build_mutant2.sh" "r2_mut$m" "$m" >> "$LOG" 2>&1
  n=$((n+1))
done
for m in C D K E F; do
  "$LEGS" "$HOME/pxperf/r2_mut$m" "$HOME/pxperf/L_r2_mut$m" \
      debug_run debug_diag cdebug_diag cdebug_down cdebug_anchor_right cdebug_anchor_down >> "$LOG" 2>&1
  TMPDIR=/home/volence/.cache/aeon-tmp python3 "$W/tools/parallax_shadow_key_witness.py" \
      --rom "$HOME/pxperf/r2_mut$m/cdebug.bin" --lst "$HOME/pxperf/r2_mut$m/cdebug.lst" \
      > "$HOME/pxperf/r2_witness_mut$m.txt" 2>&1
  echo "exit=$?" >> "$HOME/pxperf/r2_witness_mut$m.txt"
done
echo "finished=$n" >> "$LOG"
