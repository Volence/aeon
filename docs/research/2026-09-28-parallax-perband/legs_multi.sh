#!/bin/bash
# legs_multi.sh "<tag> <tag> .." <leg> [leg ..] : legs.sh over several build4.sh output dirs in turn,
#   $HOME/pxperf/<tag> -> $HOME/pxperf/L_<tag>. The last line of $HOME/pxperf/L_multi_<first tag>.log
#   is finished=<number of tags run>.
HERE=$(cd "$(dirname "$0")" && pwd)
TAGS=$1; shift
LOG=$HOME/pxperf/L_multi_${TAGS%% *}.log
n=0
for t in $TAGS; do
  "$HERE/legs.sh" "$HOME/pxperf/$t" "$HOME/pxperf/L_$t" "$@" >> "$LOG" 2>&1
  n=$((n+1))
done
echo "finished=$n" >> "$LOG"
