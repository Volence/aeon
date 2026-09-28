#!/bin/bash
# mutants3_all.sh : build_mutant3.sh for every mutant in turn (tags p4_mut<X>), then, for the
# code mutants, the canonical identity legs against the base (round 1's legs.sh into
# $HOME/pxperf/L_p4_mut<X>) and the shadow-key witness on the mutant's canonical DEBUG ROM.
# The log's last line is finished=<mutants built>.
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(cd "$HERE/../../.." && pwd)
LEGS="$HERE/../2026-09-28-parallax-perband/legs.sh"
LOG=$HOME/pxperf/p4_mut_build.log
n=0
for m in L M N P R Q S; do
  "$HERE/build_mutant3.sh" "p4_mut$m" "$m" >> "$LOG" 2>&1
  n=$((n+1))
done
find "$W/tools" -name __pycache__ -type d -prune -exec rm -rf {} +
for m in L M N P R Q; do
  "$LEGS" "$HOME/pxperf/p4_mut$m" "$HOME/pxperf/L_p4_mut$m" \
      cdebug_diag cdebug_down cdebug_run cdebug_anchor_right cdebug_anchor_down >> "$LOG" 2>&1
  TMPDIR=/home/volence/.cache/aeon-tmp timeout 1200 python3 "$W/tools/parallax_shadow_key_witness.py" \
      --rom "$HOME/pxperf/p4_mut$m/cdebug.bin" --lst "$HOME/pxperf/p4_mut$m/cdebug.lst" \
      > "$HOME/pxperf/p4_witness_mut$m.txt" 2>&1
  echo "exit=$?" >> "$HOME/pxperf/p4_witness_mut$m.txt"
done
echo "finished=$n" >> "$LOG"
