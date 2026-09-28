#!/bin/bash
# witness_runs.sh "<tag> <tag> .." : tools/parallax_shadow_key_witness.py on each tag's canonical
#   DEBUG ROM ($HOME/pxperf/<tag>/cdebug.{bin,lst}), one after another. Each run's stdout is
#   $HOME/pxperf/witness_<tag>.txt with its exit status appended; the last line of
#   $HOME/pxperf/witness_runs.log is finished=<runs>.
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(cd "$HERE/../../.." && pwd)
export TMPDIR=/home/volence/.cache/aeon-tmp
n=0
for t in $1; do
  python3 "$W/tools/parallax_shadow_key_witness.py" --rom "$HOME/pxperf/$t/cdebug.bin" \
      --lst "$HOME/pxperf/$t/cdebug.lst" > "$HOME/pxperf/witness_$t.txt" 2>&1
  echo "exit=$?" >> "$HOME/pxperf/witness_$t.txt"
  n=$((n+1))
done
echo "finished=$n" >> "$HOME/pxperf/witness_runs.log"
