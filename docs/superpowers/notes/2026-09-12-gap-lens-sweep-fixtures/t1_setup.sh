#!/bin/bash
# T1 seat scratch setup: copy the pinned worktree twice (pristine + run copy), drop the
# worktree pointer file so no VCS command in the copy can touch the real admin dir, and
# patch ONLY the copy's regenerate-level.sh repo-root resolution (it asks the VCS for the
# toplevel, which no longer exists in a pointer-less copy) to a dirname-based cd.
set -euo pipefail
SRC=/home/volence/sonic_hacks/aeon/.claude/worktrees/agent-a4695df3b8e943efc
S=$(mktemp -d /tmp/claude-1000/-home-volence-sonic-hacks-aeon/0f66baa9-0a26-4066-a435-9516186c96f8/scratchpad/t1run.XXXXXX)
echo "S=$S"
cp -a "$SRC" "$S/pristine"
rm -f "$S/pristine/.git"
cp -a "$S/pristine" "$S/nocache"
cp -a "$S/pristine" "$S/cached"
for d in nocache cached; do
  f="$S/$d/tools/regenerate-level.sh"
  python3 - "$f" <<'EOF'
import sys
p = sys.argv[1]
s = open(p).read()
old = 'cd "$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"'
assert s.count(old) == 1, "patch anchor not found exactly once"
s = s.replace(old, 'cd "$(dirname "${BASH_SOURCE[0]}")/.."')
open(p, "w").write(s)
print("patched", p)
EOF
done
echo "$S" > /tmp/claude-1000/-home-volence-sonic-hacks-aeon/0f66baa9-0a26-4066-a435-9516186c96f8/scratchpad/t1_S_path
[ -x "$S/nocache/tools/bin/salvador" ] && echo salvador_present || echo no_salvador
[ -d "$S/nocache/tools/.cache" ] && echo cache_present || echo no_cache_dir
