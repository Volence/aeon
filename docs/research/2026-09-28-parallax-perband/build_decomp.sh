#!/bin/bash
# build_decomp.sh <tag> : the four FAST shapes of HEAD with decomp.py's measurement rewrite of
# engine/level/parallax.emp applied (CONTRACTS=0: the lifted procs do not declare the
# pass-through registers, and this build is never a shipped ROM). parallax.emp must equal HEAD
# on entry (refused otherwise: the restore below is from HEAD and would eat uncommitted work),
# and is restored from HEAD on exit. Outputs $HOME/pxperf/<tag>/ like build4.sh.
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(cd "$HERE/../../.." && pwd)
cd "$W" || exit 9
F=engine/level/parallax.emp
git diff --quiet HEAD -- $F || { echo "REFUSED: $F differs from HEAD"; exit 3; }
python3 "$HERE/decomp.py" $F || { git show HEAD:$F > $F; exit 4; }
"$HERE/build4.sh" "$1"; rc=$?
git show HEAD:$F > $F
git diff --quiet HEAD -- $F && echo "restored $F from HEAD" || echo "RESTORE FAILED"
exit $rc
