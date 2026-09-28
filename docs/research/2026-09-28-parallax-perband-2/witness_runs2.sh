#!/bin/bash
# witness_runs2.sh "<tag> <tag> .." : tools/parallax_shadow_key_witness.py (this branch's copy,
#   which also compares the PPB-3/PPB-5 caches) on each tag's canonical DEBUG ROM
#   ($HOME/pxperf/<tag>/cdebug.{bin,lst}). Each run's stdout is $HOME/pxperf/w2_<tag>.txt with
#   its exit status appended; the last line of $HOME/pxperf/w2_runs.log is finished=<runs>.
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(cd "$HERE/../../.." && pwd)
export TMPDIR=/home/volence/.cache/aeon-tmp
find "$W/tools" -name __pycache__ -type d -prune -exec rm -rf {} +
n=0
for t in $1; do
  python3 "$W/tools/parallax_shadow_key_witness.py" --rom "$HOME/pxperf/$t/cdebug.bin" \
      --lst "$HOME/pxperf/$t/cdebug.lst" > "$HOME/pxperf/w2_$t.txt" 2>&1
  echo "exit=$?" >> "$HOME/pxperf/w2_$t.txt"
  n=$((n+1))
done
echo "finished=$n" >> "$HOME/pxperf/w2_runs.log"
